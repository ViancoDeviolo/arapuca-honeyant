# Arapuca HoneyAnt — Design (spec)

- **Data:** 2026-11-05 (revisão 2)
- **Status:** aguardando revisão da equipe
- **Escopo deste spec:** visão geral do sistema, contratos entre módulos e modelos técnicos (grafo, sensor, fuzzy, ACO). O detalhamento de cada módulo será feito no plano de implementação.

---

## 1. Objetivo

Ferramenta open source de segurança para casas inteligentes. Uma **isca de baixa interação** na nuvem registra ataques reais da internet. Um resumo anonimizado desses ataques alimenta um **gêmeo digital** de uma casa simulada em Docker, onde:

- um **sensor de tráfego** observa a rede da casa e **identifica** vulnerabilidades (credenciais legíveis, broker sem autenticação, ACL ausente, segmentação);
- a **lógica fuzzy** converte as evidências da isca e do sensor em risco por ligação entre dispositivos;
- um **algoritmo de colônia de formigas (ACO)** encontra o caminho de invasão mais plausível até a fechadura.

O sistema identifica uma vulnerabilidade real (credencial que os atacantes tentam + MQTT em texto puro), aplica a mitigação e **prova** o resultado com capturas `.pcap` antes/depois, com a nova leitura do sensor e com o recálculo da rota.

**Frase-guia:** roteadores avisam "você foi atacado"; o HoneyAnt avisa "é por aqui que vão te invadir, com base no que os hackers estão fazendo agora — feche isso primeiro".

### Critério de sucesso

O roteiro de demonstração (seção 13) roda de ponta a ponta, coberto por um teste E2E automatizado, e cada requisito do edital tem evidência verificável no repositório:

| Requisito | Evidência |
|---|---|
| Open Source | Repositório público, MIT, README, CONTRIBUTING.md, CODE_OF_CONDUCT.md, todo módulo entra por PR revisado |
| Telecom & Segurança de Redes | **Módulo `sensor`** monitorando o tráfego da casa; vulnerabilidade **identificada pelo sensor** e mitigada; `.pcap` antes/depois em `docs/capturas/` |
| Inteligência Computacional | Fuzzy calculando risco + ACO encontrando a rota; custo medido antes/depois |
| Arquitetura & Padrões | Diagramas em `docs/arquitetura/`, ADRs em `docs/adr/`, regra de dependência verificada no CI |
| Cloud | Isca, painel **e pathfinder** em EC2 free tier; GitHub Actions com lint e testes em todo PR |

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
EC2 (1 instância, free tier)                    Notebook da apresentação (docker compose)
┌──────────────────────────────────┐            ┌───────────────────────────────────────┐
│ arapuca ──► SQLite (volume)      │ HTTPS GET  │ twin: Mosquitto + 5 dispositivos      │
│               │ mode=ro          │ ◄───────── │ sensor + captura (rede do broker)     │
│ apps/nuvem: intel + pathfinder   │ token +    │ apps/local: pathfinder + painel       │
│             + painel             │ CA fixada  │            (formigueiro)              │
└──────────────────────────────────┘            └───────────────────────────────────────┘
```

**Security Group:**
- 23 (Telnet falso) e 1883 (MQTT falso): abertas para a internet.
- 443 (painel e `/api/v1/resumo`): **somente IPs da equipe**. A banca acessa pelo notebook da equipe. Antes da demonstração, o IP da rede do evento é adicionado (procedimento no README).
- 22 (SSH): somente o IP do responsável pelo deploy.
- **Saída bloqueada.** Para atualizar imagens, a saída é liberada temporariamente durante o deploy e fechada em seguida (procedimento no README).

Restringir a 443 também evita que um painel real ao lado da isca denuncie aos atacantes que aquilo é um honeypot.

**TLS do painel:** certificado emitido por uma **CA própria** do projeto (gerada pelo mesmo script dos certificados do Mosquitto). O cliente do notebook **fixa essa CA** (`verify="ca.pem"`) — `verify=False` é proibido e há teste que garante isso. A CA é instalada nos navegadores dos notebooks da equipe. Alternativa descartada (ADR): domínio DuckDNS + Let's Encrypt, que exige saída de rede e desafio DNS/HTTP público.

**Custo zero:** conta no Free Tier/plano de créditos e alerta de cobrança de US$ 1 criado **antes** do primeiro deploy.

**Política de uso:** verificação da política da AWS para honeypots registrada em ADR antes do deploy.

**Isolamento na EC2:** isca e painel em containers separados. O painel abre o SQLite com a URI `file:...?mode=ro`, com o usuário do container do painel sem permissão de escrita no arquivo do banco. O diretório é montado com escrita porque leitores em modo WAL precisam dos arquivos `-wal` e `-shm`. **Validado no primeiro dia** com o compose real; se falhar, o plano B é um endpoint interno da isca, acessível só pela rede Docker.

**Notebook:** a casa roda localmente. O notebook **puxa** o resumo da nuvem (a isca nunca inicia conexões). O último resumo obtido fica em cache local → plano B offline.

**Mesma imagem** nos dois lugares, com o ponto de entrada escolhido por variável de ambiente (`HONEYANT_APP=nuvem|local`).

**Banco:** SQLite em modo WAL; a isca é a única escritora. O padrão Repository isola o acesso, então PostgreSQL vira só um novo adaptador (ADR: simplicidade × paridade com produção).

## 4. Estrutura do repositório

```
arapuca-honeyant/
├── src/honeyant/
│   ├── core/         # entidades e contratos (pydantic); zero I/O
│   ├── arapuca/      # serviços falsos (Strategy), limites, repositório de eventos
│   ├── intel/        # agregação, resumo anonimizado, fuzzy de intenção
│   ├── twin/         # perfis da casa + dispositivos simulados (paho-mqtt)
│   ├── sensor/       # monitoramento de tráfego (passivo) + verificador (ativo)
│   ├── pathfinder/   # fraqueza, fuzzy de arestas, ACO, Dijkstra, snapshots
│   ├── painel/       # FastAPI, autenticação, CSP, SSE, static/ (SVG + JS puro)
│   └── apps/         # composition root: nuvem.py, local.py, cli.py
├── tests/            # unit/ integration/ e2e/ security/ performance/
├── infra/            # compose.cloud.yml, compose.local.yml, mosquitto/{inseguro,seguro}/, aws/, scripts/
├── docs/             # adr/, arquitetura/, contratos/, capturas/, demo/, superpowers/
├── .github/workflows/ci.yml
└── README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE
```

- **Um único pacote Python** (um `pyproject.toml`, um CI, uma configuração de lint): publicar vários pacotes seria cerimônia sem ganho neste prazo.
- **Regra de dependência:** `core` não importa nada do projeto; cada módulo importa apenas `core`; **módulos nunca importam uns aos outros** e se comunicam pelos contratos. **Só `apps/` (composition root) importa vários módulos**, para montá-los num processo. Verificado no CI com **import-linter**.
  - `apps/nuvem.py`: arapuca + intel + pathfinder + painel (modo nuvem).
  - `apps/local.py`: pathfinder + painel (modo local), lendo resumo, perfil e evidências.
  - `apps/cli.py`: comandos `honeyant mitigar`, `honeyant verificar`, `honeyant gravar-replay`.
- **Hexagonal dentro de cada módulo:** `ports.py` (interfaces/Protocols) + `adapters/` + casos de uso. Mesmo formato em todos os módulos.

## 5. Módulos

| Módulo | Roda em | Entrada | Saída | Padrões |
|---|---|---|---|---|
| `arapuca` | EC2 | Conexões TCP em 23 e 1883 | `EventoDeAtaque` no SQLite | Strategy (um serviço falso por protocolo), Repository |
| `intel` | EC2 | Eventos do SQLite (`mode=ro`) | `ResumoDeAmeaca` em `GET /api/v1/resumo` | Repository, fuzzy de intenção |
| `twin` | Notebook | Perfil da casa (`inseguro`/`seguro`) + `.env` | Dispositivos falando MQTT real com o Mosquitto | Adapter (cliente MQTT) |
| `sensor` | Notebook | Tráfego da rede do broker + resumo | `EvidenciaDeRede` (JSON em volume) | Adapter (fonte de tráfego: ao vivo ou `.pcap`), Observer |
| `pathfinder` | EC2 e notebook | Perfil + evidências + resumo | `Rota` + `Snapshot` por iteração | Strategy (ACO/Dijkstra), Observer (snapshots) |
| `painel` | EC2 e notebook | Resumo, rotas, snapshots | Mapa de ataques, rota, formigueiro (SSE) | Observer/Pub-Sub, Adapter (fonte do resumo: HTTP ou cache) |

**Isca (`arapuca`) — regras:** baixa interação (só simulação em Python; sem shell, sem sistema de arquivos, sem execução); Telnet falso pede login/senha e aceita alguns comandos como texto, respondendo com saídas fixas; MQTT falso registra o CONNECT (usuário/senha) e tópicos de PUBLISH/SUBSCRIBE. Limites de taxa por IP, de conexões simultâneas, de tamanho de payload e de tempo de sessão. **Teto global de armazenamento** (200.000 eventos ou 200 MB, o que vier primeiro), com descarte dos mais antigos. País/ASN via base **offline DB-IP Lite (CC-BY 4.0)** embutida na imagem, com atribuição no README e no rodapé do painel.

**Fuzzy de intenção (`intel`):** entradas — diversidade de credenciais tentadas, número de comandos após o login, taxa de conexões; saída — `varredura`, `forca_bruta` ou `botnet`. Sistema pequeno, separado do fuzzy de arestas.

### Sensor (`sensor`)

É o **módulo de monitoramento de tráfego** da casa. O perfil descreve como a casa está configurada; o sensor **gera a evidência** observando-a.

- **Passivo:** container com Scapy em `network_mode: service:mosquitto` (enxerga todo o tráfego de/para o broker). Decodifica pacotes MQTT CONNECT na 1883: se usuário e senha aparecem legíveis, registra `texto_puro = true` e o SHA-256 da senha observada para aquela origem. Tráfego na 8883 aparece apenas como TLS → `texto_puro = false`, sem credencial observada.
- **Ativo (`honeyant verificar`):** a partir de um container na rede de cada dispositivo,
  - tenta conectar ao broker **sem credenciais** → `autenticacao_exigida`;
  - tenta conectar com as **20 credenciais mais tentadas na isca** → `credencial_vazada` (ataque de dicionário controlado contra a própria casa);
  - com a credencial do dispositivo, tenta publicar no tópico da fechadura → `acl_bloqueia`;
  - testa conexão TCP com o broker → `alcancavel` (detecta a segmentação).
- Grava `EvidenciaDeRede` em JSON num volume lido pelo pathfinder.
- O mesmo adaptador de tráfego lê `.pcap` gravados, o que permite testar o parser sem rede.

### Captura (`infra`)

Docker Desktop no Windows roda os containers dentro de uma VM, então **o Wireshark do host não vê o tráfego entre os containers**. Um container `captura` com tcpdump, também em `network_mode: service:mosquitto`, grava `.pcap` num volume, que depois é aberto no Wireshark. Para ver ao vivo, o comando é executado no **Git Bash ou no cmd** (o pipe do PowerShell 5.1 corrompe dados binários):

```
docker exec captura tcpdump -U -w - | "C:\Program Files\Wireshark\Wireshark.exe" -k -i -
```

**Testado em 05/11 ou 06/11 no notebook da apresentação.**

## 6. Contratos (`core`)

Modelos pydantic com `schema_version`. O CI exporta o JSON Schema de cada modelo para `docs/contratos/`. **Fixtures de exemplo** de `ResumoDeAmeaca`, perfis da casa e `EvidenciaDeRede` entram junto com os contratos, para que pathfinder e painel avancem sem depender de isca, twin e sensor prontos.

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
  por_servico: dict[servico, int]               # janela de 24 h (sobe e desce)
  acumulado_por_servico: dict[servico, int]     # contador monotônico desde o início; só o modo ao vivo usa
  por_pais: dict[str, int]; por_asn: dict[int, int]
  intencao: dict[varredura | forca_bruta | botnet, int]
  top_credenciais: list[{usuario, senha, tentativas}]   # top 20; nenhum IP

PerfilDaCasa            # configuração declarativa lida por twin, sensor e pathfinder
  perfil: inseguro | seguro; origem = "internet"; alvo = "fechadura"
  nos:     list[{id, tipo, rotulo, x, y, sensibilidade}]
  arestas: list[{origem, destino, servico, exposicao, fraqueza_fixa: int | None}]
           # fraqueza_fixa só para arestas que o sensor não observa (lan, upnp, telnet da internet)

EvidenciaDeRede         # sensor → pathfinder (uma por aresta observada)
  aresta: "a->b"; observado_em; fonte: passivo | ativo
  texto_puro: bool | None
  credencial_vazada: bool | None      # senha observada ou aceita pertence ao top 20 da isca
  autenticacao_exigida: bool | None
  acl_bloqueia: bool | None
  alcancavel: bool | None

Rota                    # nos: list[str]; custo: float; plausibilidade: float; algoritmo: aco | dijkstra
Snapshot                # execucao_id, semente, iteracao, feromonio: dict["a->b", float],
                        # caminhos: list[list[str]] (≤ 20), melhor: Rota | None
```

`servico` ∈ {`telnet`, `mqtt`, `http`, `upnp`, `lan`}. A isca só observa `telnet` e `mqtt`; os demais têm frequência 0.

`None` numa evidência significa "não observado". Quando há mais de uma evidência para a mesma aresta, os campos são combinados: um valor observado sempre substitui `None`, e em conflito vale a evidência **ativa** mais recente (ela testa de fato; a passiva só infere). O pathfinder trata ausência de evidência de forma **conservadora** (assume o pior) e o painel mostra o que foi observado e o que foi assumido.

**O contador acumulado** fica numa tabela própria no SQLite, incrementada a cada evento gravado e nunca apagada pela retenção. Assim o modo ao vivo não perde nem duplica formigas quando eventos antigos saem da janela.

## 7. Modelo da casa

```
                 [Internet]
                 /        \
          telnet (9)     upnp (7)
               /              \
         [Câmera]          [Roteador] ─────────── mqtt (5) ──────────┐
             \            /     |     \                              │
          mqtt (6)  [Lâmpada] [Tomada] [Termostato]   (lan, 5)       │
               \        |        |        /                          │
                └──► [Broker Mosquitto] ◄──┘  (mqtt, 5) ◄────────────┘
                            |
                       mqtt (4)
                            |
                      [Fechadura]  ← alvo
```

Grafo dirigido com 8 nós (número entre parênteses = exposição 0–10). As coordenadas (x, y) de cada nó ficam no perfil e definem o layout fixo do formigueiro.

| Configuração | Perfil `inseguro` | Perfil `seguro` |
|---|---|---|
| Credencial da câmera | **a mais tentada no resumo congelado** (`docs/demo/resumo-congelado.json`) | forte, gerada pelo script |
| MQTT | 1883, texto puro, anônimo permitido, sem ACL | 8883 com TLS, autenticação e ACL |
| Câmera | mesma rede do broker | rede Docker isolada (sem rota até o broker) |

**Credencial da câmera e resumo congelado:** o perfil inseguro não depende do top 20 do dia. Ele usa a credencial mais tentada de um resumo salvo e versionado, o mesmo usado na demonstração e no teste E2E. Na apresentação: "configuramos a câmera com a senha que os atacantes mais tentaram".

**Origem das senhas reais:** `infra/scripts/gerar-segredos.py` gera localmente `.env`, o `mosquitto_passwd` e a CA/certificados — **nada disso é versionado**. O perfil versionado não contém senhas.

## 8. Pesos das arestas: fraqueza → fuzzy → custo

**Fraqueza da aresta (0–10), função pura sobre a `EvidenciaDeRede` da aresta:**

| Condição | Pontos |
|---|---|
| `credencial_vazada` | +4 |
| `texto_puro` | +3 |
| não `autenticacao_exigida` | +2 |
| não `acl_bloqueia` | +1 |

(limitada a 10; `None` conta como verdadeiro para condições de risco — postura conservadora. Arestas que o sensor não observa — `lan`, `upnp` e o `telnet` vindo da internet — usam `fraqueza_fixa` do perfil.)

Se `alcancavel = false`, a aresta é **bloqueada**: sai do grafo (custo infinito).

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

R1–R3 garantem que toda entrada dispara ao menos uma regra.

**Monotonicidade:** Mamdani com centroide **não garante** que aumentar uma entrada nunca reduza o risco (R7 convive com R1, por exemplo). Por isso o teste de monotonicidade roda numa **grade 11 × 11 × 11** de entradas **em 06/11**; se falhar, regras e funções de pertinência são ajustadas cedo, e o ajuste é registrado.

**Faixa do risco:** o centroide fica aproximadamente entre 0,1 e 0,9, então o risco é comprimido nas pontas. Isso é esperado e documentado; o que importa é a **ordem** entre as arestas.

**Custo da aresta = −ln(risco)**, com risco limitado a [0,001; 0,999] — portanto o custo é sempre positivo e o depósito `Q / custo` do ACO nunca divide por zero. O custo da rota é a soma dos custos. **`plausibilidade = e^(−custo)`** é o produto dos riscos fuzzy das arestas: um **score relativo** para comparar rotas, **não** uma probabilidade calibrada.

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

**Por que ACO se o Dijkstra resolve?** O feromônio mostra as rotas alternativas e o quanto cada uma é plausível, não só a melhor; o ACO se readapta conforme novas evidências chegam; e é o que torna o formigueiro possível.

**Snapshots:** o ACO aceita observadores; o emissor de snapshots é um deles. O domínio não sabe que está sendo desenhado.

**Na nuvem:** o pathfinder é Python puro e barato, então o painel em modo nuvem também roda "Prever invasão" e o replay, usando o resumo atual, o perfil versionado e as evidências gravadas da última verificação (fixture versionada). Assim o núcleo do sistema também está implantado em nuvem.

## 10. Vulnerabilidade: identificação e mitigação

1. A isca coleta as credenciais tentadas; o resumo congelado define a credencial da câmera no perfil inseguro.
2. **O sensor identifica**: o passivo vê o CONNECT da câmera com usuário e senha legíveis na 1883; o ativo confirma que o broker aceita conexão anônima, que a credencial está entre as mais tentadas e que nada impede a câmera de publicar no tópico da fechadura. A captura `docs/capturas/antes.pcap` mostra o mesmo no Wireshark.
3. Fraqueza alta em câmera→broker e broker→fechadura → o ACO aponta `internet → câmera → broker → fechadura`.
4. `honeyant mitigar` (padrão **Command**) troca para o perfil `seguro`: credencial forte, MQTT/TLS na 8883, autenticação + ACL no Mosquitto, câmera em rede Docker isolada. Reinicia broker e dispositivos e roda `honeyant verificar` de novo.
5. O sensor passa a ver só TLS, a conexão anônima e o dicionário são recusados, a ACL bloqueia e a câmera não alcança o broker → aresta câmera→broker bloqueada. Nova captura `docs/capturas/depois.pcap` com tráfego cifrado. O ACO recalcula: a melhor rota restante (pelo roteador) tem custo maior.

Os `.pcap` versionados contêm **apenas credenciais geradas para a demonstração**, nunca senhas reais da equipe.

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
1. **Ao vivo:** o painel local consulta o resumo a cada 10 s; para cada aumento em `acumulado_por_servico`, solta uma formiga de ataque daquele serviço. Nenhum evento individual sai da nuvem.
2. **Prever invasão:** roda o ACO iteração a iteração; velocidade ajustável (0,25× a 4×).
3. **Replay:** reproduz um `.jsonl` de snapshots gravado com semente fixa — plano B offline.

**Resumo congelado para a demonstração:** a rota é calculada sobre `docs/demo/resumo-congelado.json`, enquanto as formigas de ataque ao vivo continuam chegando por cima. Assim um pico de ataques não muda a rota no meio da apresentação.

**Transporte:** `GET /api/v1/formigueiro/stream?modo=…&semente=42&velocidade=1` via Server-Sent Events, eventos `snapshot` e `ataque`; no máximo um snapshot a cada 150 ms e no máximo 20 formigas desenhadas. Front em SVG + JavaScript puro com `requestAnimationFrame`; sem biblioteca de grafo (D3 só com ADR justificando).

## 12. Segurança

**Isca:** baixa interação; saída bloqueada no SG; limites de taxa, conexões, payload, tempo de sessão e armazenamento total; toda entrada é hostil — validada, truncada e escapada antes de persistir ou exibir.

**Painel e API:**
- 443 aberta só para IPs da equipe (seção 3).
- Autenticação com usuário único e senha forte via variável de ambiente; **5 tentativas erradas por IP → bloqueio de 15 minutos**; sessão em cookie `HttpOnly`/`Secure`/`SameSite=Strict`; sem rotas administrativas expostas.
- `/api/v1/resumo` exige token Bearer; o cliente fixa a CA do projeto; `verify=False` proibido (teste).
- Endpoint SSE exige a mesma autenticação do painel.
- CSP sem scripts inline; dados da isca inseridos só com `textContent`, nunca `innerHTML`.

**Segredos:** só em `.env` local (gerado por script), variáveis de ambiente e GitHub Secrets; gitleaks no CI. Dependências fixadas; `pip-audit` e bandit no CI.

**Sobre o SHA-256 no perfil e nas evidências:** SHA-256 sem salt de senha fraca é quebrado por dicionário em segundos. Ele é usado para **não versionar senhas**, não como medida de proteção, e é apresentado assim.

**LGPD:** IP de atacante é dado pessoal — fica só no SQLite da EC2, com retenção de 7 dias (limpeza periódica); tudo que sai da EC2 é agregado por país/ASN.

## 13. Roteiro da demonstração (~5 min)

1. Painel na nuvem: ataques reais por serviço, senha e país.
2. Casa simulada: o sensor aponta "credencial legível, broker anônimo, sem ACL"; o Wireshark mostra a mesma credencial no `.pcap`.
3. Formigueiro: formigas cavam até a fechadura passando pela câmera.
4. `honeyant mitigar` com o formigueiro na tela.
5. Túnel da câmera desmorona; formigas buscam outro caminho, mais caro. O sensor e o novo `.pcap` mostram só TLS.
6. Repositório: PRs revisados e pipeline verde.

**Plano B:** `docker compose` local, resumo congelado e em cache, `.pcap` salvos, replay do formigueiro e vídeo gravado.

## 14. Testes

| Tipo | Cobertura |
|---|---|
| Unitário | Funções de pertinência e regras fuzzy; **monotonicidade na grade 11³**; função de fraqueza; tratamento de `None`; ACO converge e coincide com o Dijkstra em ≥ 95% de 20 sementes; snapshots coerentes (evaporação reduz, reforço aumenta); parsers Telnet/MQTT da isca; **parser MQTT do sensor sobre `.pcap` gravado**; validação dos contratos |
| Determinismo | Mesma semente → mesma sequência de snapshots |
| Integração | isca → SQLite → resumo, com o painel lendo em `mode=ro` no compose real; contador acumulado sobrevive à retenção; dispositivos ↔ Mosquitto nos perfis inseguro e seguro; verificador ativo nos dois perfis; cliente SSE recebe snapshots |
| E2E | Resumo congelado + perfil inseguro + semente 42 → sensor identifica a vulnerabilidade e a rota passa pela câmera; `mitigar` → evidências mudam, rota muda e custo sobe |
| Segurança | Payloads maliciosos na isca (binário, oversized, XSS, injeção de comandos); flood respeita o teto de armazenamento; XSS no painel; bloqueio do login; cliente recusa certificado fora da CA; bandit, gitleaks, pip-audit |
| Desempenho | Isca sob carga de conexões simultâneas; tempo de convergência do ACO |

## 15. CI/CD

GitHub Actions em todo PR e push em `main`: ruff (lint + formatação), import-linter, pytest (unit + integration com Mosquitto como serviço), bandit, gitleaks, pip-audit, exportação de JSON Schema. Branch `main` protegida: merge só com CI verde e uma aprovação. Deploy da EC2 manual e documentado (script em `infra/aws/`).

## 16. Equipe e revisão

| Módulo | Dono | Revisor (e substituto) |
|---|---|---|
| `core` (contratos), `apps/`, CI, deploy AWS | Lucas | todos aprovam os contratos |
| `arapuca` | Lucas | Rafael |
| `intel` + `sensor` | Rafael | Kauã |
| `twin` + captura + perfis | Kawe | Lucas |
| `pathfinder` | Kauã | Gustavo |
| `painel` + formigueiro | Gustavo | Kawe |

Critério: **quem consome revisa quem produz**. O revisor também é o **substituto** do módulo, porque já conhece o código — assim não há um único ponto de falha. O Lucas continua sendo o apoio geral.

## 17. Cronograma

| Quando | Entrega |
|---|---|
| 05/11 | Spec e plano; esqueleto do repositório, CI e isca no ar; teste do container de captura no notebook da apresentação |
| 06/11 manhã | Contratos e fixtures do `core` aprovados por todos; teste do `mode=ro` na EC2 |
| 06/11 tarde | **Esqueleto ponta a ponta sobre as fixtures**: perfil → evidência de fixture → fuzzy → ACO → SSE → SVG simples, rodando em `apps/local`. Cada dono entrega a versão mais fina do seu módulo; teste E2E mínimo verde. Teste de monotonicidade na grade |
| 07/11 | Cada um aprofunda o seu módulo **sobre algo que já funciona**: sensor real, twin real, formigueiro completo, capturas antes/depois |
| 08/11 | E2E completo, diagramas, README; **corte às 18h**; ensaio |
| 09/11 | Projeto congelado |

Se parte da equipe não conseguir entregar, o esqueleto de 06/11 é o que permite fechar o projeto com menos gente.

## 18. ADRs previstos

1. Arquitetura hexagonal, regra de dependência e composition root (`apps/`)
2. Topologia: isca, painel e pathfinder na EC2; casa e sensor no notebook
3. SQLite no MVP (vs PostgreSQL) e leitura em `mode=ro`
4. Isca de baixa interação (vs Cowrie) e política de uso da AWS
5. TLS com CA própria fixada (vs DuckDNS + Let's Encrypt)
6. Sensor passivo + verificador ativo como fonte das evidências
7. Custo da aresta como −ln(risco) e plausibilidade como score relativo
8. ACO com Dijkstra como gabarito
9. SSE em vez de WebSocket
10. SVG + JS puro em vez de framework/D3

## 19. Riscos

| Risco | Mitigação |
|---|---|
| Integração entre 5 pessoas falha no fim | Contratos + fixtures em 06/11 de manhã; esqueleto ponta a ponta em 06/11 à tarde |
| Wireshark do host não vê o tráfego dos containers | Container `captura` com tcpdump; testado no notebook da apresentação em 05–06/11 |
| SQLite WAL falha em leitura somente leitura | Teste no compose real em 06/11; plano B: endpoint interno da isca |
| Rota da demo muda com os dados do dia | Resumo congelado e versionado define a credencial da câmera e a rota |
| Teste de monotonicidade falha | Rodado em 06/11; ajuste de regras e pertinências cedo |
| Isca recebe poucos ataques | Sobe em 05/11; Telnet na 23 recebe varredura em minutos; fixtures garantem a demonstração mesmo assim |
| Força bruta no painel / painel denuncia o honeypot | 443 só para IPs da equipe; bloqueio após 5 tentativas |
| Disco da EC2 enche com flood | Teto global de eventos e bytes com descarte dos mais antigos |
| Internet da sala falha | Resumo em cache, replay e vídeo |
| Cobrança na AWS | Uma instância, alerta de US$ 1, saída bloqueada |
| ACO não converge para a rota esperada | Dijkstra como gabarito no teste; parâmetros ajustáveis; semente fixa |
| Algum integrante sem conseguir explicar outra parte | Revisão cruzada por consumidor (revisor = substituto) + ADRs curtos e didáticos |
