# Arapuca HoneyAnt — Design (spec)

- **Data:** 2026-11-05
- **Status:** aguardando revisão da equipe
- **Escopo deste spec:** visão geral do sistema, contratos entre módulos e modelos técnicos (grafo, fuzzy, ACO). O detalhamento de cada módulo será feito no plano de implementação.

---

## 1. Objetivo

Ferramenta open source de segurança para casas inteligentes. Uma **isca de baixa interação** na nuvem registra ataques reais da internet. Um resumo anonimizado desses ataques alimenta um **gêmeo digital** de uma casa simulada em Docker, onde:

- a **lógica fuzzy** converte evidências em risco por ligação entre dispositivos;
- um **algoritmo de colônia de formigas (ACO)** encontra o caminho de invasão mais provável até a fechadura.

O sistema demonstra uma vulnerabilidade real (credencial fraca + MQTT em texto puro), aplica a mitigação e **prova** o resultado com capturas `.pcap` antes/depois e com o recálculo da rota.

**Frase-guia:** roteadores avisam "você foi atacado"; o HoneyAnt avisa "é por aqui que vão te invadir, com base no que os hackers estão fazendo agora — feche isso primeiro".

### Critério de sucesso

O roteiro de demonstração (seção 12) roda de ponta a ponta, coberto por um teste E2E automatizado, e cada requisito do edital tem evidência verificável no repositório:

| Requisito | Evidência |
|---|---|
| Open Source | Repositório público, MIT, README, CONTRIBUTING.md, CODE_OF_CONDUCT.md, todo módulo entra por PR revisado |
| Telecom & Segurança de Redes | Monitoramento de tráfego (isca + capturas), vulnerabilidade mitigada, `.pcap` antes/depois em `docs/capturas/` |
| Inteligência Computacional | Fuzzy calculando risco + ACO encontrando a rota; custo medido antes/depois |
| Arquitetura & Padrões | Diagramas em `docs/arquitetura/`, ADRs em `docs/adr/`, regra de dependência verificada no CI |
| Cloud | Isca e painel em EC2 free tier; GitHub Actions com lint e testes em todo PR |

## 2. Escopo

**Dentro (até o congelamento):** toda a P1 do briefing + **Formigueiro ao vivo**.

**Fora, em fila de extras (nesta ordem):**
1. Assistente de IA no painel (somente leitura, padrão Command)
2. Painel HTTP falso de câmera na isca
3. Feed aberto
4. Alertas pelo Telegram

**Regras para extras:** só entram depois que P1 + formigueiro estiverem integrados e testados; entram por PR revisado com testes e CI verde; **último merge de funcionalidade nova em 08/11 às 18h** — depois disso só correções e ensaio.

## 3. Topologia de implantação

```
EC2 (1 instância, free tier)                  Notebook da apresentação (docker compose)
┌─────────────────────────────────┐           ┌──────────────────────────────────────┐
│ arapuca ──► SQLite (volume)     │ HTTPS GET │ twin: Mosquitto + 5 dispositivos     │
│               │ montado RO      │ ◄──────── │ pathfinder: fuzzy + ACO + snapshots  │
│ painel (modo nuvem) + intel     │ com token │ painel (modo local): formigueiro     │
└─────────────────────────────────┘           └──────────────────────────────────────┘
```

- **Security Group:** entrada 23 (Telnet falso), 1883 (MQTT falso), 443 (painel); SSH (22) só do IP do responsável. **Saída bloqueada.** Para atualizar imagens, a saída é liberada temporariamente durante o deploy e fechada em seguida (procedimento no README).
- **Custo zero:** conta no Free Tier/plano de créditos e alerta de cobrança de US$ 1 criado **antes** do primeiro deploy.
- **Política de uso:** verificação da política da AWS para honeypots registrada em ADR antes do deploy.
- **Isolamento na EC2:** isca e painel em containers separados; o volume do SQLite é montado **somente leitura** no painel.
- **Notebook:** a casa roda localmente porque as capturas do Wireshark são feitas na máquina da demonstração. O notebook **puxa** o resumo da nuvem (a isca nunca inicia conexões). O último resumo obtido fica em cache local → plano B offline.
- **Mesma imagem do painel** nos dois lugares, com modo definido por variável de ambiente (`HONEYANT_MODO=nuvem|local`).

**Banco:** SQLite em modo WAL; a isca é a única escritora. O padrão Repository isola o acesso, então PostgreSQL vira só um novo adaptador (ADR: simplicidade × paridade com produção).

## 4. Estrutura do repositório

```
arapuca-honeyant/
├── src/honeyant/
│   ├── core/         # entidades e contratos (pydantic); zero I/O
│   ├── arapuca/      # serviços falsos (Strategy), limites, repositório de eventos
│   ├── intel/        # agregação, resumo anonimizado, fuzzy de intenção
│   ├── twin/         # perfis da casa + dispositivos simulados (paho-mqtt)
│   ├── pathfinder/   # fraqueza, fuzzy de arestas, ACO, Dijkstra, snapshots
│   └── painel/       # FastAPI, autenticação, CSP, SSE, static/ (SVG + JS puro)
├── tests/            # unit/ integration/ e2e/ security/ performance/
├── infra/            # compose.cloud.yml, compose.local.yml, mosquitto/{inseguro,seguro}/, aws/
├── docs/             # adr/, arquitetura/, contratos/, capturas/, superpowers/
├── .github/workflows/ci.yml
└── README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE
```

- **Um único pacote Python** (um `pyproject.toml`, um CI, uma configuração de lint): publicar seis pacotes seria cerimônia sem ganho neste prazo.
- **Regra de dependência:** `core` não importa nada do projeto; cada módulo importa apenas `core`; **módulos nunca importam uns aos outros** e se comunicam só pelos contratos (HTTP, MQTT, arquivos JSON). Verificado no CI com **import-linter**.
- **Hexagonal dentro de cada módulo:** `ports.py` (interfaces/Protocols) + `adapters/` + casos de uso. Mesmo formato em todos os módulos.

## 5. Módulos

| Módulo | Roda em | Entrada | Saída | Padrões |
|---|---|---|---|---|
| `arapuca` | EC2 | Conexões TCP em 23 e 1883 | `EventoDeAtaque` no SQLite | Strategy (um serviço falso por protocolo), Repository |
| `intel` | EC2 (no processo do painel) | Eventos do SQLite (RO) | `ResumoDeAmeaca` em `GET /api/v1/resumo` | Repository, fuzzy de intenção |
| `twin` | Notebook | Perfil da casa (`inseguro`/`seguro`) | Dispositivos falando MQTT real com o Mosquitto | Adapter (cliente MQTT) |
| `pathfinder` | Notebook | `GrafoDaCasa` + `ResumoDeAmeaca` | `Rota` + `Snapshot` por iteração | Strategy (ACO/Dijkstra), Observer (snapshots) |
| `painel` | EC2 e notebook | Resumo, rotas, snapshots | Mapa de ataques, rota, formigueiro (SSE) | Observer/Pub-Sub, Adapter (fonte do resumo: HTTP ou cache) |

**Isca (`arapuca`) — regras:** baixa interação (só simulação em Python; sem shell, sem sistema de arquivos, sem execução); Telnet falso pede login/senha e aceita alguns comandos como texto, respondendo com saídas fixas; MQTT falso registra o CONNECT (usuário/senha) e tópicos de PUBLISH/SUBSCRIBE. Limites de taxa por IP, de conexões simultâneas, de tamanho de payload e de tempo de sessão. País/ASN via base **offline DB-IP Lite (CC-BY)** embutida na imagem.

**Fuzzy de intenção (`intel`):** entradas — diversidade de credenciais tentadas, número de comandos após o login, taxa de conexões; saída — `varredura`, `forca_bruta` ou `botnet`. Sistema pequeno, separado do fuzzy de arestas.

## 6. Contratos (`core`)

Modelos pydantic com `schema_version`. O CI exporta o JSON Schema de cada modelo para `docs/contratos/`. **Fixtures de exemplo** de `ResumoDeAmeaca` e `GrafoDaCasa` entram junto com os contratos, para que pathfinder e painel avancem sem depender de isca e twin prontos.

```python
EventoDeAtaque          # arapuca → SQLite (nunca sai da EC2)
  id: UUID; ts: datetime (UTC); servico: telnet | mqtt
  ip_origem             # dado pessoal; retenção de 7 dias
  pais: str | None      # ISO 3166-1 alfa-2
  asn: int | None
  usuario, senha: str | None        # truncados em 64 caracteres
  comandos: list[str]               # ≤ 20 itens, ≤ 256 caracteres cada
  bytes_recebidos: int

ResumoDeAmeaca          # intel → notebook (GET /api/v1/resumo, token Bearer)
  gerado_em; janela_horas = 24; total_eventos
  por_servico: dict[servico, int]
  por_pais: dict[str, int]; por_asn: dict[int, int]
  intencao: dict[varredura | forca_bruta | botnet, int]
  top_credenciais: list[{usuario, senha, tentativas}]   # top 20; nenhum IP

GrafoDaCasa             # perfil declarativo lido por twin e pathfinder
  perfil: inseguro | seguro; origem = "internet"; alvo = "fechadura"
  nos:     list[{id, tipo, rotulo, x, y, sensibilidade, credencial: {usuario, sha256_senha} | None}]
  arestas: list[{origem, destino, servico, exposicao, texto_puro, autenticacao, acl, bloqueada}]

Rota                    # nos: list[str]; custo: float; probabilidade: float; algoritmo: aco | dijkstra
Snapshot                # execucao_id, semente, iteracao, feromonio: dict["a->b", float],
                        # caminhos: list[list[str]] (≤ 20), melhor: Rota | None
```

`servico` ∈ {`telnet`, `mqtt`, `http`, `upnp`, `lan`}. A isca só observa `telnet` e `mqtt`; os demais têm frequência 0.

**O grafo nunca contém senha em texto puro** — só o SHA-256. O pathfinder calcula o SHA-256 das senhas de `top_credenciais` e compara.

## 7. Modelo da casa

```
              [Internet]
              /        \
       telnet (9)    upnp (7)
            /            \
      [Câmera]        [Roteador]
          \           /    |     \
       mqtt (6)  [Lâmpada] [Tomada] [Termostato]   (lan, 5)
            \        |        |        /
             └──► [Broker Mosquitto] ◄──┘           (mqtt, 5)
                         |
                    mqtt (4)
                         |
                   [Fechadura]  ← alvo
```

Grafo dirigido com 8 nós (número entre parênteses = exposição 0–10). O roteador também tem aresta `mqtt` direta para o broker. As coordenadas (x, y) de cada nó ficam no perfil e definem o layout fixo do formigueiro.

| Atributo | Perfil `inseguro` | Perfil `seguro` |
|---|---|---|
| Credencial da câmera | presente na lista de senhas tentadas | forte, aleatória |
| MQTT | 1883, texto puro, sem autenticação/ACL | 8883 com TLS, autenticação e ACL |
| Câmera | mesma rede do broker | rede Docker isolada → aresta câmera→broker `bloqueada` |

## 8. Pesos das arestas: fraqueza → fuzzy → custo

**Fraqueza do destino (0–10), função pura:**

| Condição | Pontos |
|---|---|
| SHA-256 da credencial do destino aparece em `top_credenciais` | +4 |
| `texto_puro` | +3 |
| sem `autenticacao` | +2 |
| sem `acl` | +1 |

(limitada a 10)

**Frequência (0–1):** `por_servico[servico] / total_eventos` (0 se o serviço não é observado pela isca ou se `total_eventos = 0`).

**Exposição (0–10):** atributo da aresta no perfil.

**Fuzzy de arestas (Mamdani, scikit-fuzzy):** entradas com termos baixa/média/alta (funções triangulares e trapezoidais); saída `risco` ∈ [0, 1] com termos baixo/médio/alto/crítico; defuzzificação por centroide. Regras iniciais:

| # | Se | Então risco |
|---|---|---|
| R1 | fraqueza baixa | baixo |
| R2 | fraqueza média | médio |
| R3 | fraqueza alta | alto |
| R4 | fraqueza alta E exposição alta | crítico |
| R5 | fraqueza alta E frequência alta | crítico |
| R6 | fraqueza média E frequência alta | alto |
| R7 | fraqueza baixa E exposição alta E frequência alta | médio |
| R8 | exposição baixa E frequência baixa | baixo |

R1–R3 garantem que toda entrada dispara ao menos uma regra. Propriedade testada: **monotonicidade** — aumentar qualquer entrada nunca reduz o risco.

**Custo da aresta = −ln(risco)**, com risco limitado a [0,001; 1]. Aresta `bloqueada` é removida do grafo (custo infinito). O custo da rota é a soma dos custos, e `probabilidade = e^(−custo)` é o produto dos riscos — a chance de todos os passos darem certo.

## 9. Algoritmos de rota

**ACO (Ant System clássico):** heurística η = risco; probabilidade de escolha ∝ τ^α · η^β; formigas não revisitam nós; formiga que chega a beco sem saída é descartada; depósito Q / custo da rota; evaporação global.

| Parâmetro | Valor inicial |
|---|---|
| Formigas | 20 |
| Iterações | 50 |
| α | 1 |
| β | 2 |
| ρ (evaporação) | 0,1 |
| τ₀ | 0,1 |
| Q | 1 |
| Semente | 42 (configurável) |

**Dijkstra** sobre os mesmos custos dá a rota ótima exata e serve de **gabarito nos testes**. Ambos implementam a mesma interface `AlgoritmoDeRota` (Strategy).

**Por que ACO se o Dijkstra resolve?** O feromônio mostra as rotas alternativas e o quanto cada uma é provável, não só a melhor; o ACO se readapta conforme novas evidências chegam; e é o que torna o formigueiro possível.

**Snapshots:** o ACO aceita observadores; o emissor de snapshots é um deles. O domínio não sabe que está sendo desenhado.

## 10. Vulnerabilidade e mitigação

1. A isca coleta as credenciais tentadas.
2. No perfil `inseguro`, a câmera usa uma delas e o MQTT trafega em texto puro na 1883 → captura `docs/capturas/antes.pcap` com usuário, senha e comandos legíveis.
3. Fraqueza alta na câmera → o ACO aponta `internet → câmera → broker → fechadura`.
4. `honeyant mitigar` (padrão **Command**) troca para o perfil `seguro`: credencial forte, MQTT/TLS na 8883, autenticação + ACL no Mosquitto, câmera em rede Docker isolada. Reinicia broker e dispositivos.
5. Nova captura `docs/capturas/depois.pcap` com tráfego cifrado; o ACO recalcula: a aresta câmera→broker está bloqueada e a melhor rota restante (pelo roteador) tem custo maior.

Certificados TLS gerados localmente por script (CA própria); **nunca versionados** (`.gitignore` já cobre).

## 11. Formigueiro ao vivo

| Sistema | Formigueiro |
|---|---|
| Internet | Entrada na superfície |
| Dispositivo | Câmara subterrânea (ícone + nome via `textContent`) |
| Fechadura | Câmara mais funda, destacada |
| Aresta | Túnel; espessura e brilho ∝ feromônio |
| Evaporação | Túnel afina e apaga |
| Formiga do ACO | Ponto animado |
| Ataque real | Formiga de cor de acento entrando pela superfície |
| Rota prevista | Túnel principal contínuo em cor de alerta |
| Mitigação | Túnel desmorona (tracejado, bloqueado) |

Cor nunca é o único canal: espessura, tracejado e legenda também.

**Modos:**
1. **Ao vivo:** o painel local consulta o resumo a cada 10 s; para cada aumento em `por_servico`, solta uma formiga de ataque daquele serviço. Nenhum evento individual sai da nuvem.
2. **Prever invasão:** roda o ACO iteração a iteração; velocidade ajustável (0,25× a 4×).
3. **Replay:** reproduz um `.jsonl` de snapshots gravado com semente fixa — plano B offline.

**Resumo congelado para a demonstração:** a rota é calculada sobre um resumo salvo com data/hora, enquanto as formigas de ataque ao vivo continuam chegando por cima. Assim um pico de ataques não muda a rota no meio da apresentação.

**Transporte:** `GET /api/v1/formigueiro/stream?modo=…&semente=42&velocidade=1` via Server-Sent Events, eventos `snapshot` e `ataque`; no máximo um snapshot a cada 150 ms e no máximo 20 formigas desenhadas. Front em SVG + JavaScript puro com `requestAnimationFrame`; sem biblioteca de grafo (D3 só com ADR justificando).

## 12. Roteiro da demonstração (~5 min)

1. Painel na nuvem: ataques reais por serviço, senha e país.
2. Casa simulada + Wireshark com credenciais MQTT legíveis.
3. Formigueiro: formigas cavam até a fechadura passando pela câmera.
4. `honeyant mitigar` com o formigueiro na tela.
5. Túnel da câmera desmorona; formigas buscam outro caminho, mais caro. Captura cifrada.
6. Repositório: PRs revisados e pipeline verde.

**Plano B:** `docker compose` local, resumo em cache, `.pcap` salvos, replay do formigueiro e vídeo gravado.

## 13. Segurança

**Isca:** baixa interação; saída bloqueada no SG; limites de taxa, conexões, payload e tempo de sessão; toda entrada é hostil — validada, truncada e escapada antes de persistir ou exibir.

**Aplicação:**
- Painel com autenticação (usuário único, senha via variável de ambiente, sessão em cookie `HttpOnly`/`Secure`/`SameSite=Strict`); sem rotas administrativas expostas.
- Endpoint de resumo exige token Bearer; endpoint SSE exige a mesma autenticação do painel.
- CSP sem scripts inline; dados da isca inseridos só com `textContent`, nunca `innerHTML`.
- Segredos só em variáveis de ambiente e GitHub Secrets; gitleaks no CI.
- Dependências fixadas; `pip-audit` e bandit no CI.

**LGPD:** IP de atacante é dado pessoal — fica só no SQLite da EC2, com retenção de 7 dias (limpeza periódica); tudo que sai da EC2 é agregado por país/ASN.

## 14. Testes

| Tipo | Cobertura |
|---|---|
| Unitário | Funções de pertinência e regras fuzzy (incluindo monotonicidade); função de fraqueza; ACO converge e coincide com o Dijkstra em ≥ 95% de 20 sementes; snapshots coerentes (evaporação reduz, reforço aumenta); parsers Telnet/MQTT da isca; validação dos contratos |
| Determinismo | Mesma semente → mesma sequência de snapshots |
| Integração | isca → SQLite → resumo; dispositivos ↔ Mosquitto (perfis inseguro e seguro); cliente SSE recebe snapshots |
| E2E | Perfil inseguro + semente 42 → rota passa pela câmera; `mitigar` → rota muda e custo sobe |
| Segurança | Payloads maliciosos na isca (binário, oversized, XSS, injeção de comandos); XSS no painel; bandit, gitleaks, pip-audit |
| Desempenho | Isca sob carga de conexões simultâneas; tempo de convergência do ACO |

## 15. CI/CD

GitHub Actions em todo PR e push em `main`: ruff (lint + formatação), import-linter, pytest (unit + integration com Mosquitto como serviço), bandit, gitleaks, pip-audit, exportação de JSON Schema. Branch `main` protegida: merge só com CI verde e uma aprovação. Deploy da EC2 manual e documentado (script em `infra/aws/`).

## 16. Equipe e revisão

| Módulo | Dono | Revisor |
|---|---|---|
| `core` (contratos), CI, deploy AWS | Lucas | todos aprovam os contratos |
| `arapuca` | Lucas | Rafael |
| `intel` | Rafael | Kauã |
| `twin` + vulnerabilidade + capturas | Kawe | Lucas |
| `pathfinder` | Kauã | Gustavo |
| `painel` + formigueiro | Gustavo | Kawe |

Critério: **quem consome revisa quem produz.** Lucas é o substituto de qualquer módulo em caso de imprevisto.

## 17. Cronograma

| Quando | Entrega |
|---|---|
| 05/11 | Spec e plano; esqueleto do repositório, CI e isca no ar |
| 06/11 manhã | Contratos e fixtures do `core` aprovados por todos |
| 06/11 | Cada integrante no seu módulo |
| 07/11 | Integração; formigueiro; capturas antes/depois |
| 08/11 | E2E, diagramas, README; **corte às 18h**; ensaio |
| 09/11 | Projeto congelado |

## 18. ADRs previstos

1. Arquitetura hexagonal e regra de dependência entre módulos
2. Topologia: isca/painel na EC2, casa no notebook
3. SQLite no MVP (vs PostgreSQL)
4. Isca de baixa interação (vs Cowrie) e política de uso da AWS
5. Custo da aresta como −ln(risco)
6. ACO com Dijkstra como gabarito
7. SSE em vez de WebSocket
8. SVG + JS puro em vez de framework/D3

## 19. Riscos

| Risco | Mitigação |
|---|---|
| Integração entre 5 pessoas falha no fim | Contratos + fixtures no 06/11 de manhã; integração começa em 07/11, não em 08/11 |
| Isca recebe poucos ataques | Sobe em 05/11; Telnet na 23 recebe varredura em minutos; fixtures garantem a demonstração mesmo assim |
| Internet da sala falha | Resumo em cache, replay e vídeo |
| Cobrança na AWS | Uma instância, alerta de US$ 1, saída bloqueada |
| ACO não converge para a rota esperada | Dijkstra como gabarito no teste; parâmetros ajustáveis; semente fixa |
| Rota muda no meio da apresentação | Resumo congelado para a demonstração |
| Algum integrante sem conseguir explicar outra parte | Revisão cruzada por consumidor + ADRs curtos e didáticos |
