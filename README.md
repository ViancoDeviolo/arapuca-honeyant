# Arapuca HoneyAnt

> Roteadores avisam "você foi atacado". O HoneyAnt avisa "é por aqui que vão te invadir — feche isso primeiro".

Ferramenta open source de segurança para casas inteligentes:

- uma **isca de baixa interação** na nuvem (Telnet e MQTT falsos) registra ataques reais da internet;
- um **gêmeo digital** de uma casa simulada em Docker usa um resumo anonimizado desses ataques;
- um **sensor de tráfego** identifica a vulnerabilidade na casa a partir das capturas;
- **lógica fuzzy** transforma as evidências em risco por ligação entre dispositivos. A isca
  mostra o que os ataques reais estão mirando e ajusta a plausibilidade; a rota é decidida
  pelas fraquezas medidas na casa
  ([ADR 0005, sensibilidade medida](docs/adr/0005-custo-da-aresta-e-fuzzy.md#sensibilidade-medida-0911));
- um **algoritmo de colônia de formigas (ACO)** prevê o caminho de invasão mais plausível até a fechadura, desenhado como um formigueiro.

O nome junta *arapuca* (armadilha brasileira) e *honeypot ant* (formiga-pote-de-mel).

Projeto da ExpoTech UniFECAF (28/11/2026). Arquitetura em [`docs/arquitetura/`](docs/arquitetura/), decisões em [`docs/adr/`](docs/adr/).

## Como rodar a demo

Requisitos: [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows) ou Docker Engine com Compose (Linux) e Node 20+ só para os testes JS.

```bash
git clone https://github.com/ViancoDeviolo/arapuca-honeyant.git
cd arapuca-honeyant
uv sync
```

**1. Painel com a rota prevista** (não precisa de Docker):

```bash
uv run honeyant-local          # abra http://127.0.0.1:8000
```

Clique em **Prever invasão**: as formigas exploram a casa e a rota Internet → Câmera → Broker →
Fechadura aparece em destaque. **Aplicar mitigação** derruba o túnel da câmera e recalcula: a
nova rota passa pelo roteador e é **31× menos plausível**. **Replay** mostra a mesma história a
partir de arquivos gravados (plano B offline).

**2. Casa simulada, mitigação real e capturas** (Docker aberto):

```bash
uv run honeyant-twin preparar  # senhas, CA e certificados de teste (fora do git)
uv run honeyant-twin subir     # perfil inseguro: MQTT 1883 sem TLS, sem senha, sem ACL
uv run honeyant-mitigar        # perfil seguro: 8883 com TLS, senha forte, ACL, câmera isolada
uv run honeyant-mitigar --desfazer
uv run honeyant-capturar       # grava docs/capturas/antes.pcap e depois.pcap (~1 min)
uv run honeyant-twin descer
```

**3. Sensor identificando a vulnerabilidade:**

```bash
uv run honeyant-sensor docs/capturas/antes.pcap    # camera->broker: texto puro e credencial vazada
uv run honeyant-sensor docs/capturas/depois.pcap   # nenhum MQTT em texto puro
```

No PowerShell os comandos são os mesmos. O passo a passo das capturas, com o filtro do
Wireshark, está em [`docs/capturas/LEIAME.md`](docs/capturas/LEIAME.md).

### Aplicativo ao vivo (Windows)

Para a equipe e a banca: um `HoneyAnt.exe` que abre o painel com os **ataques da isca
chegando ao vivo** ([ADR 0011](docs/adr/0011-empacotamento-pyinstaller.md)).

1. Baixe o `HoneyAnt.exe` pelo link que o Lucas mandar e deixe na área de trabalho.
2. Dois cliques. Se aparecer **"O Windows protegeu o computador"** (o app não tem assinatura
   de código): **Mais informações → Executar assim mesmo**.
3. Na primeira vez, cole a **chave de acesso** que o Lucas mandou e tecle Enter (ou só Enter
   para usar o resumo guardado). Ela fica em `%APPDATA%\HoneyAnt\config.json`.
4. O navegador abre sozinho no painel (`http://127.0.0.1:8765`). Para sair, feche a janela
   preta do app.

O cabeçalho mostra de onde vêm os dados: **"Ao vivo · atualizado às HH:MM"** (a sua rede
alcança a isca); **"Resumo de <data>, offline"** (sem acesso: o último resumo guardado); ou
o resumo que veio no app. A porta 443 da isca só aceita IPs cadastrados: em outra rede, o app
fica offline sem travar. Chave errada: "chave de acesso inválida", o app para de tentar e
esquece a chave salva; feche, abra de novo e cole a chave certa.

**Plano B** (se o Defender bloquear o `.exe`): pelo código-fonte, `uv run honeyant-local`
(painel completo, sem o ao vivo). Pelo código-fonte, `uv run honeyant-app` também abre, mas
fica sempre offline: o endereço da isca (`app.json`) e a CA (`ca.crt`) só existem dentro do
`.exe`.

**Antes de distribuir um `.exe` novo** (Lucas), no PowerShell:

1. Varredura do Defender:
   `& "$env:ProgramFiles\Windows Defender\MpCmdRun.exe" -Scan -ScanType 3 -File "$PWD\dist\HoneyAnt.exe"`
   — esperado: "found no threats". Se acusar algo, não distribua: anote o nome da detecção e
   use o plano B.
2. Teste do SmartScreen como os outros vão ver: suba o `.exe` no Drive, baixe de volta (o
   arquivo baixado ganha a marca "veio da internet") e abra. Deve aparecer "O Windows protegeu
   o computador" → "Mais informações" → "Executar assim mesmo", e o painel abre.
3. Com a sua chave e o IP liberado na 443, o cabeçalho tem que mostrar "Ao vivo".

**Para gerar o `.exe`** (Lucas): `uv run honeyant-certificados --ip <ip-elastico>`, copiar
`infra/app/app-local.exemplo.json` para `infra/app/app-local.json` com o IP e rodar
`powershell -ExecutionPolicy Bypass -File infra/app/construir.ps1`. O resumo-api da EC2 está
em `infra/aws/DEPLOY.md`, seção 7.2.

### Login do painel

```bash
uv run honeyant-hash-senha            # pede a senha e imprime o hash (nunca a senha)
export HONEYANT_PAINEL_SENHA_HASH="<hash>"            # Linux
# PowerShell: $env:HONEYANT_PAINEL_SENHA_HASH = "<hash>"
uv run honeyant-local
```

Com `HONEYANT_PAINEL_SENHA_HASH`, a página e a API exigem login (botão **Sair** no topo).
Sem ela, o painel abre sem login, mas só aceita conexões da própria máquina (127.0.0.1).
Um hash inválido impede o painel de subir. O cookie de sessão é `Secure` por padrão; se o
navegador recusar o cookie em `http://127.0.0.1`, use `HONEYANT_PAINEL_COOKIE_SEGURO=0`.

### Testes

```bash
uv run pytest -m "not integration"          # unitários e E2E (o que o CI roda)
uv run pytest -m integration                # brokers de verdade (precisa do Docker)
node --test tests/js/*.test.mjs             # funções puras do painel
uv run ruff check . && uv run lint-imports  # estilo e regra de dependência
```

No PowerShell, os testes JS são `node --test (Get-ChildItem tests/js/*.test.mjs)`.

## Arquitetura

Hexagonal: contratos no `core`, módulos que só dependem do `core`, e o `apps/` como
*composition root* ([ADR 0001](docs/adr/0001-arquitetura-hexagonal.md)). Diagramas de
contexto, componentes, sequência da demo e implantação em
[`docs/arquitetura/`](docs/arquitetura/README.md).

| Módulo | Faz | Padrões |
|---|---|---|
| `arapuca` | Isca: Telnet e MQTT falsos, grava eventos no SQLite | Strategy (um serviço por protocolo), Repository |
| `intel` | Agrega os eventos num resumo sem IPs; fuzzy de intenção | Repository |
| `twin` | Planta da casa e configuração dos dois perfis | — (funções puras) |
| `sensor` | Lê `.pcap` e gera `EvidenciaDeRede` | Adapter (`FonteDeTrafego`) |
| `pathfinder` | Fuzzy de risco por aresta, ACO e Dijkstra | Strategy, Observer (snapshots) |
| `painel` | API, SSE e o formigueiro em SVG | Portas/Adapter, Observer (SSE) |
| `apps/` | Comandos `honeyant-*` | Composition root, Command (`honeyant-mitigar`) |

## Requisitos do edital → evidência

| Requisito | Onde está |
|---|---|
| **Open Source** | Repositório público, [MIT](LICENSE), este README, [CONTRIBUTING.md](CONTRIBUTING.md), [Código de Conduta](CODE_OF_CONDUCT.md); módulos entregues por PR revisado ([pull requests](https://github.com/ViancoDeviolo/arapuca-honeyant/pulls?q=is%3Apr)) |
| **Segurança de redes** | Monitoramento de tráfego: [`sensor/`](src/honeyant/sensor/); vulnerabilidade real (MQTT em texto puro e sem autenticação) identificada pelo sensor e mitigada por [`honeyant-mitigar`](src/honeyant/apps/mitigar.py); capturas [`antes.pcap`](docs/capturas/antes.pcap) (36 `CONNECT` com senha legível) e [`depois.pcap`](docs/capturas/depois.pcap) (só TLS); testes de integração dos brokers em [`tests/integration/test_twin_brokers.py`](tests/integration/test_twin_brokers.py) |
| **Inteligência computacional** | Fuzzy de risco ([ADR 0005](docs/adr/0005-custo-da-aresta-e-fuzzy.md)) e ACO com Dijkstra como gabarito ([ADR 0006](docs/adr/0006-aco-com-dijkstra-gabarito.md)) em [`pathfinder/`](src/honeyant/pathfinder/); custo antes 1,42 e depois 4,86 (31× menos plausível), travado em [`tests/e2e/`](tests/e2e/) |
| **Arquitetura e padrões** | [Diagramas](docs/arquitetura/README.md), [ADRs](docs/adr/), import-linter no CI |
| **Cloud e CI/CD** | Isca na EC2 ([deploy](infra/aws/DEPLOY.md), [ADR 0002](docs/adr/0002-topologia-isca-na-ec2-casa-no-notebook.md)); [CI](.github/workflows/ci.yml) em todo PR: ruff, formatação, import-linter, bandit, pytest (inclui os testes do servidor da isca), testes JS, gitleaks e pip-audit. Deploy (CD) manual por decisão de segurança: a saída da EC2 fica bloqueada e um CD automático exigiria credenciais da AWS no GitHub e saída aberta; cada deploy é uma janela registrada no CloudTrail ([DEPLOY.md, seção 4.1](infra/aws/DEPLOY.md#41-registro-das-janelas-de-saída-da-ec2)) |

## Segurança e ética da isca

- **Baixa interação** ([ADR 0004](docs/adr/0004-isca-baixa-interacao.md)): Telnet e MQTT
  simulados em Python, sem shell, sem sistema de arquivos e sem execução de comandos.
- **Saída bloqueada:** o Security Group não tem regra de saída. A isca nunca inicia
  conexões; a saída é aberta só durante o deploy e fechada em seguida.
- **Container sem privilégios:** usuário sem root, sistema de arquivos somente leitura,
  sem *capabilities*, limites de memória, processos, sessão e taxa por IP.
- **LGPD:** IP de atacante é dado pessoal. Fica só no SQLite da EC2, com retenção de 7 dias
  e teto de armazenamento. Tudo que sai de lá é agregado (país, ASN, serviço, credenciais
  tentadas), sem IP. O leitor abre o banco em `mode=ro`, com outro usuário.
- **Entrada hostil:** tudo que vem da isca é validado, truncado e limpo antes de gravar ou
  mostrar. O painel usa só `textContent` e uma CSP sem script inline.
- **Capturas:** contêm só credenciais de teste geradas para a demo.

### Registro das janelas de saída da EC2

A saída fica bloqueada o tempo todo e só é aberta (HTTP/HTTPS) durante instalações e
deploys. As seis janelas abertas até agora (14, 5, 47, 1, 2 e 12 minutos), com data, hora e motivo,
tiradas do CloudTrail, estão em
[`infra/aws/DEPLOY.md`, seção 4.1](infra/aws/DEPLOY.md#41-registro-das-janelas-de-saída-da-ec2).

## Equipe

| Integrante | Responsabilidade |
|---|---|
| Lucas | `core` (contratos), `arapuca`, `pathfinder` (fuzzy, ACO, Dijkstra), `painel` e formigueiro, twin (configuração, mitigação e capturas), `apps/`, CI, deploy na AWS e documentação; implementação final de `intel` e `sensor` |
| Rafael | `intel` e `sensor`; periféricos da apresentação |
| Kawe | `twin`: planta da casa (`twin/planta.py`); revisão do PR #20 |
| Kauã | `pathfinder`: replay determinístico (`adapters/replay.py`) e ADRs 0005 e 0006 |
| Gustavo | `painel`: login (hash scrypt, sessão, limite de tentativas); revisão do PR #19 |

Critério de revisão: quem consome revisa quem produz.

## Dívidas técnicas conhecidas

- **Modo nuvem do painel:** não existe. Na EC2 há só o resumo-api (agregado, chave
  obrigatória); o painel roda em 127.0.0.1 no notebook ou no app
  ([ADR 0002](docs/adr/0002-topologia-isca-na-ec2-casa-no-notebook.md)). Se um painel for para a
  nuvem, ele deve **recusar subir sem `HONEYANT_PAINEL_SENHA_HASH`**.
- **Ao vivo só no app:** o `honeyant-local` usa o resumo congelado (formigas num ritmo fixo);
  o ao vivo, com uma formiga por ataque novo, é o `HoneyAnt.exe` com o resumo-api.
- **Chave de acesso do app em texto** em `%APPDATA%\HoneyAnt\config.json`; no futuro,
  proteger com DPAPI.
- **App sem assinatura de código:** SmartScreen avisa; o Defender pode dar falso positivo
  (plano B: `uv run honeyant-local`).
- **Sessões e bloqueios do login em memória:** reiniciar o painel derruba as sessões.
- **Dispositivos do twin** reconectam a cada publicação; o sensor não remonta fluxos TCP
  ([ADR 0010](docs/adr/0010-twin-e-sensor-sem-dependencias-novas.md)).
- **Evidências da demo** (`docs/demo/evidencias-*.json`) são fixtures calibradas; o sensor
  concorda com elas no `antes.pcap` (teste), mas ainda não as gera.
- **Peso da isca no risco:** a frequência de ataques só pesa no fuzzy quando passa de ~50%
  dos ataques num serviço; nesta casa ela muda a plausibilidade, não a rota. Recalibrar as
  funções de pertinência da frequência
  ([ADR 0005, sensibilidade medida](docs/adr/0005-custo-da-aresta-e-fuzzy.md#sensibilidade-medida-0911)).

## Próximos passos (roadmap)

As limitações acima são conhecidas e medidas. Aqui elas estão agrupadas por objetivo, cada uma
com o motivo de ter ficado para depois e o primeiro passo. Sem datas: nenhum item foi
prometido para a ExpoTech.

**Inteligência computacional**

- **Isca pesando também abaixo de 50% dos ataques.** Hoje ela muda a plausibilidade, não a
  rota ([ADR 0005, sensibilidade medida](docs/adr/0005-custo-da-aresta-e-fuzzy.md#sensibilidade-medida-0911);
  [`test_sensibilidade_a_isca.py`](tests/e2e/test_sensibilidade_a_isca.py)). Ficou para
  depois porque recalibrar muda os custos da demo. Primeiro passo: medir a sensibilidade de
  novo numa casa maior.
- **ACO × Dijkstra em casas maiores.** O [ADR 0006](docs/adr/0006-aco-com-dijkstra-gabarito.md)
  mediu a casa da demo (8 nós) e a auditoria final estendeu até 12. Primeiro passo: gerar
  casas sintéticas maiores e repetir a comparação.
- **Intenção como entrada do risco.** O fuzzy de intenção do intel
  ([`intel/intencao.py`](src/honeyant/intel/intencao.py)) hoje só informa o painel. Ficou
  para depois porque exige regras novas no fuzzy de risco. Primeiro passo: medir se a
  intenção muda a rota antes de propor as regras.

**Segurança de redes**

- **Evidências da demo geradas pelo sensor** direto do `.pcap` (hoje são fixtures
  calibradas, conferidas com o sensor no `antes.pcap`). Primeiro passo: gravar a saída do
  sensor no formato de `docs/demo/evidencias-*.json` e comparar com as fixtures.
- **Remontagem de fluxos TCP e leitura de interface ao vivo** no sensor. A porta
  `FonteDeTrafego` já prevê outras fontes
  ([ADR 0010](docs/adr/0010-twin-e-sensor-sem-dependencias-novas.md)). Primeiro passo: um
  adapter de interface ao vivo atrás da mesma porta.
- **Credenciais vazadas vindas também da isca**, quando ela capturar pares completos (hoje
  vêm da lista de fábrica, [`docs/demo/LEIAME.md`](docs/demo/LEIAME.md)). O código já une as
  duas fontes ([`core/credenciais.py`](src/honeyant/core/credenciais.py)); falta a isca
  capturar pares completos.

**Cloud e CI/CD**

- **CD com aprovação manual** (GitHub Environments + OIDC, sem chave da AWS guardada), que
  abra e feche a janela de saída sozinho e fique registrado no CloudTrail. Mantém a decisão de
  segurança atual ([ADR 0002](docs/adr/0002-topologia-isca-na-ec2-casa-no-notebook.md)).
  Primeiro passo: um papel IAM com OIDC restrito ao Security Group da isca.
- **Actions fixadas por SHA e imagens por digest** no Dockerfile e no compose da nuvem (o
  twin já está fixado). Primeiro passo: trocar as tags do [`ci.yml`](.github/workflows/ci.yml).
- **Testes dos brokers no CI** ([`test_twin_brokers.py`](tests/integration/test_twin_brokers.py)),
  que precisam de Docker. Primeiro passo: um job separado com Docker no runner do GitHub.

**Painel e aplicativo**

- **Modo nuvem do painel**, que recusa subir sem `HONEYANT_PAINEL_SENHA_HASH` (ver Dívidas
  técnicas). Ficou para depois porque a demo roda no notebook.
- **Sessões e bloqueios do login persistidos** (hoje em memória;
  [ADR 0009](docs/adr/0009-login-do-painel.md)).
- **Chave do app protegida com DPAPI e executável assinado** (hoje o SmartScreen avisa;
  [ADR 0011](docs/adr/0011-empacotamento-pyinstaller.md)).

**Escala**

- **Escrita em lote na isca, ou outro banco,** se o tráfego passar de ~500 sessões/s (medido
  na auditoria final; hoje são centenas de sessões por dia;
  [ADR 0003](docs/adr/0003-sqlite-no-mvp.md)).

Contribuições são bem-vindas: veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o [Código de Conduta](CODE_OF_CONDUCT.md).

## Licença

[MIT](LICENSE).

## Atribuições

IP Geolocation by DB-IP (https://db-ip.com), licença [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).
