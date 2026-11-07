# Aplicativo HoneyAnt ao vivo (.exe) — design (spec)

- **Data:** 2026-11-07
- **Status:** aprovado pelo Lucas em 07/11, com as 7 condições da seção 9 e os ajustes da seção 11
- **Prazo:** pronto e estável até **08/11 às 18h**; senão sai do escopo (seção 9, condição 7)

## 1. Objetivo

Um arquivo único para **Windows** (`HoneyAnt.exe`) que a equipe e a banca baixam, deixam na
área de trabalho e, ao abrir, mostra o painel do HoneyAnt com os **ataques da isca chegando
ao vivo**. Sem internet, ou sem acesso à EC2, o app continua funcionando com o último resumo
conhecido.

**Critério de sucesso:**
- dois cliques no `.exe` abrem o painel no navegador, sem instalar Python, uv nem Docker;
- com a chave de acesso e o IP liberado, o cabeçalho mostra "Ao vivo" e as formigas de
  ataque saem a cada ataque novo registrado na isca;
- sem acesso à EC2, o app não trava: mostra "resumo de <data>, offline" (cache) ou o resumo
  embutido;
- nenhuma mudança na isca (`arapuca`), e a porta nova não aparece para quem não está na
  lista de IPs.

**Fora do escopo:** twin, capturas e sensor (precisam de Docker e ficam só na máquina de
quem apresenta); macOS e Linux; assinatura de código; atualização automática do app.

## 2. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Onde roda o painel | No app, em `127.0.0.1` da máquina de quem usa | Nenhum painel ao lado da isca; o navegador não fala com a EC2 (sem aviso de certificado) |
| O que a EC2 serve | Só `GET /api/v1/resumo` (agregado, sem IP) | Menor superfície possível |
| Servidor na EC2 | `http.server` + `ssl` da biblioteca padrão | A imagem da isca não tem FastAPI; nenhuma dependência nova |
| Rota da demo | Calculada sobre o resumo **embutido** | O ao vivo só alimenta cartões e formigas; a rota não muda no meio da apresentação (spec-mãe, 11) |
| Empacotamento | PyInstaller, versão fixada, `--onefile` (ADR 0011) | Gera um `.exe` só, sem instalar Python |

## 3. Arquitetura

```
Máquina de quem usa (Windows)                       EC2 (Security Group: 443 só para IPs cadastrados)
┌──────────────────────────────────────────┐        ┌────────────────────────────────────────┐
│ HoneyAnt.exe                             │ HTTPS  │ resumo-api (usuário 10002, mode=ro)     │
│  ├ painel em 127.0.0.1:<porta livre>     │ ─────► │  GET /api/v1/resumo  (Bearer)           │
│  ├ FonteDoResumoAoVivo                   │ CA     │  agrega 24 h, máscara de IPv4, cache 15s│
│  │   ao vivo → cache → embutido          │ fixada │            │                            │
│  ├ CA do projeto (pública, embutida)     │        │  SQLite da isca (só leitura)            │
│  └ fixtures + resumo + replays embutidos │        │ isca (inalterada): 23 e 1883            │
└──────────────────────────────────────────┘        └────────────────────────────────────────┘
       navegador ──http──► 127.0.0.1
```

### 3.1 EC2: `resumo-api`

- **Comando:** `honeyant-servir-resumo` (em `apps/`), no container `resumo-api` do
  `infra/compose.cloud.yml`, com a imagem da isca.
- **Container:** o processo roda como `10002:10001` e escuta em **8443** (porta alta: não
  precisa de root nem de `CAP_NET_BIND_SERVICE`); o compose mapeia `443:8443`. `read_only`,
  `tmpfs /tmp`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit: 128m`, `pids_limit: 64`.
- **Banco:** `LeitorSqlite` em `mode=ro` (o mesmo arranjo do `verificar-ro`, validado em 06/11).
- **Rotas:** só `GET /api/v1/resumo`. Qualquer outra rota ou método: `404` com corpo vazio.
  Cabeçalho `Server` genérico (`honeyant`), sem versão.
- **Resposta:** `ResumoDeAmeaca` das últimas 24 h, pelo mesmo `agregar` do intel (máscara de
  IPv4 incluída), sem campo extra (o contrato não aceita); o `gerado_em` diz quando foi
  calculado. Guardado em memória por **15 s**.
- **Acesso:**
  - `Authorization: Bearer <chave>`; a EC2 guarda só o **hash scrypt** da chave;
  - comparação em **tempo constante** (`hmac.compare_digest` sobre o resultado do scrypt);
  - **5 erros por IP em 15 min bloqueiam por 15 min** (os números do login do painel);
    durante o bloqueio, `429` sem nem verificar a chave;
  - **sem o hash no ambiente, o serviço recusa subir** (login obrigatório na nuvem).
- **TLS:** TLS 1.2 ou superior; certificado do servidor emitido pela CA do projeto, com o IP
  elástico da EC2 no SAN e **validade de 90 dias**. A renovação (novo certificado com a mesma
  CA, `scp` e reinício do `resumo-api`, sem novo `.exe`) fica documentada no DEPLOY.
- **Logs:** uma linha JSON por requisição (`status`, `rota`, duração); nunca a chave nem o
  cabeçalho `Authorization`.

### 3.2 Segredos

| Segredo | Onde fica | Quem gera |
|---|---|---|
| Chave de acesso (texto) | Com o Lucas; entregue a cada pessoa por fora (WhatsApp); no app, em `%APPDATA%\HoneyAnt\config.json` | `honeyant-chave-app` |
| Hash da chave | EC2, `~/arapuca-honeyant/infra/resumo-api.env`, dono **o usuário do deploy** (quem lê o `env_file` é o `docker compose`, não o container), permissão `600` | `honeyant-chave-app` |
| Chave privada da **CA** | **Só no PC do Lucas**, `%USERPROFILE%\.honeyant\ca\ca.key`, fora do repositório; nunca vai para a EC2 | `honeyant-certificados` |
| Certificado público da CA | Embutido no `.exe` (não é segredo) | `honeyant-certificados` |
| Certificado e chave do servidor | EC2, `~/arapuca-honeyant/infra/certs-resumo/`, dono `10002`, `600` na chave | `honeyant-certificados`, copiados por `scp` |
| URL da EC2 (com o IP) | **Não é segredo.** Fica em `infra/app/app-local.json`, fora do git por organização, e entra no `.exe` no build | o Lucas |

Nada disso entra em commit. O `.gitignore` cobre `*.key`, `*.pem`, `*.crt`, `.env*` e
`infra/app/app-local.json`; o gitleaks no CI continua valendo.

A EC2 tem **IP elástico** (associado desde 05/11): o IP não muda ao parar e ligar. O IP não
é tratado como segredo: as proteções são o Security Group, a chave de acesso e o TLS.

### 3.3 App: `HoneyAnt.exe`

- **Entrada:** `honeyant-app` (`apps/aplicativo.py`).
- **Ao abrir:**
  1. lê `%APPDATA%\HoneyAnt\config.json`; sem chave, pergunta no console
     ("Cole a chave de acesso. Enter para usar só o resumo guardado.") e salva;
  2. sobe o painel **só em `127.0.0.1`** (nunca `0.0.0.0`), na porta 8765; se ela estiver
     ocupada, tenta as 9 seguintes; se todas estiverem ocupadas, mostra "As portas 8765 a 8774
     estão ocupadas. Feche outro HoneyAnt aberto e tente de novo." e sai;
  3. abre o navegador padrão nessa URL sozinho;
  4. o console fica aberto com o estado ("Ao vivo", "offline") e "Feche esta janela para
     sair".
- **Dados embutidos:** `docs/demo/` (perfis, evidências, resumo real mais recente, replays),
  estáticos do painel e o certificado da CA. Caminhos resolvidos por `sys._MEIPASS` quando
  empacotado.
- **Porta `FonteDoResumo` nova:** `FonteDoResumoAoVivo` (adapter em `apps/`), com três
  níveis:
  1. **ao vivo:** `GET <url>/api/v1/resumo` com timeout de 5 s, no máximo uma vez a cada
     15 s; sucesso grava o cache. **Erro de rede:** recuo exponencial (15 s, 30 s, 60 s…, teto
     de 5 min), que volta a 15 s no primeiro sucesso. **401:** o app **para de consultar**
     até ser reaberto e mostra "chave de acesso inválida"; assim ele nunca chega aos 5 erros
     que bloqueiam o IP;
  2. **cache:** `%APPDATA%\HoneyAnt\ultimo-resumo.json`, o último resumo ao vivo recebido;
  3. **embutido:** o `resumo-real-*.json` mais recente que veio no `.exe`.
  Uma falha nunca bloqueia a página: o painel responde na hora com o nível disponível.
- **Verificação TLS do cliente:** `ssl.create_default_context(cafile=<CA embutida>)`, com
  `check_hostname=True`, `verify_mode=CERT_REQUIRED` e `minimum_version=TLSv1_2`. O host da
  URL é o IP, e o Python confere o IP no SAN. Só a CA do projeto é aceita.
- **Contrato `ResumoComOrigem`:** `origem` ganha `"ao_vivo"` e `"offline"` além de `"real"` e
  `"exemplo"`, e o campo opcional `atualizado_em`.

### 3.4 Painel (front)

- **Cabeçalho e cartão "Ataques reais":** "Ao vivo · atualizado às HH:MM" /
  "Resumo de <data>, offline" / "Ataques reais, congelados em <data>" / "Dados de exemplo".
- **Atualização:** a página consulta `/api/v1/resumo` a cada 15 s.
- **Formigas de ataque:**
  - ao vivo: uma formiga por aumento de `acumulado_por_servico` desde a consulta anterior
    (no máximo 6 por vez), do serviço que aumentou;
  - fora do ao vivo: o ritmo atual (uma a cada 2 s, sorteada na proporção do resumo);
  - com "reduzir movimento": nenhuma.
- A **rota** (Prever, Mitigar, Replay e "Antes e depois") continua sobre o resumo embutido.

## 4. Empacotamento (ADR 0011)

- **PyInstaller**, versão fixada, rodado só no build
  (`uv run --with pyinstaller==6.22.3 pyinstaller ...`): não entra nas dependências do
  projeto.
- `--onefile --console --name HoneyAnt`, com `--add-data` para `docs/demo`, os estáticos do
  painel e a CA, e o `app-local.json` (URL).
- Script: `infra/app/construir.ps1`. Saída: `dist/HoneyAnt.exe`. `build/`, `dist/` e `*.spec`
  ficam no `.gitignore`.
- Distribuição: por link direto (Drive ou WhatsApp), só para a equipe e a banca. O `.exe`
  **nunca** vai para o repositório nem para Releases do GitHub.

**Defender e SmartScreen:** um `.exe` sem assinatura baixado da internet recebe a marca
"veio da internet" e o SmartScreen mostra "O Windows protegeu o computador" → "Mais
informações" → "Executar assim mesmo". O teste da seção 7 cobre isso de propósito.

## 5. Tratamento de erros

| Situação | Comportamento |
|---|---|
| EC2 fora do ar, IP não liberado, rede da faculdade bloqueando | Timeout de 5 s → cache → embutido; cabeçalho "offline"; nova tentativa com recuo exponencial (teto de 5 min) |
| Chave errada (401) | Para de consultar até o app ser reaberto; cache ou embutido; cabeçalho e console mostram "chave de acesso inválida" |
| Bloqueado por tentativas (429) | Segue offline; console avisa que tente de novo em 15 min |
| Certificado de outra CA ou de outro IP | Recusa a conexão (nunca aceita); segue offline; console: "certificado não confere" |
| Resposta inválida (não valida no contrato) | Descarta; segue com o nível anterior |
| Porta local ocupada | Tenta 8765 a 8774; todas ocupadas → mensagem clara e sai |
| `config.json` corrompido | Pergunta a chave de novo |

## 6. Segurança (resumo)

- A isca não muda. A porta 443 só existe para os IPs cadastrados no Security Group.
- Login obrigatório na nuvem (o serviço não sobe sem o hash), tempo constante, 5/15 min.
- Só leitura no banco (`mode=ro`, usuário `10002`).
- Nenhum IP de atacante sai (agregado + máscara de IPv4).
- Nenhuma chave no `.exe` nem no repositório; só a CA pública vai embutida.
- TLS 1.2+, CA fixada, IP conferido no SAN; `verify=False` e `check_hostname=False`
  proibidos (teste que procura esses textos no código).

## 7. Testes

**Unitários (CI):**
- `resumo-api`: sem `Authorization` → 401; chave errada → 401; 5 erros → 429 por 15 min
  (relógio injetado); chave certa → 200 com `ResumoDeAmeaca` válido e sem IPv4; rota ou
  método desconhecido → 404 vazio; cache de 15 s; o `main()` sem o hash falha ao subir.
- `FonteDoResumoAoVivo`: sucesso grava o cache; falha de rede → cache com origem
  `"offline"`; sem cache → embutido; timeout não trava (servidor que nunca responde);
  **depois de um 401 nenhuma requisição nova** (o servidor de teste conta as chamadas);
  **recuo exponencial** com teto (relógio injetado); resposta inválida descartada.
- App: o servidor faz bind **só em `127.0.0.1`**; porta ocupada → próxima; todas ocupadas →
  mensagem clara.
- **TLS de verdade** (certificados gerados no teste com `openssl`; o CI tem; pula se não
  houver): CA certa + IP certo → conecta; **certificado emitido para outro IP → recusa**;
  certificado de outra CA → recusa; servidor só com TLS 1.1 → recusa.
- Varredura do código: nenhum `verify=False`, `check_hostname = False` nem
  `CERT_NONE`.
- JS: `novosAtaques(anterior, atual)` (diferença do acumulado, no máximo 6) e o texto do
  cabeçalho para cada origem.

**Manual no notebook do Lucas (08/11):**
1. `infra/app/construir.ps1` gera o `.exe`;
2. abrir o `.exe` local (sem a marca de internet): painel abre, "offline" sem chave;
3. com a chave e o IP liberado: "Ao vivo"; confirmar formigas quando o acumulado sobe;
4. tirar a internet: em até 20 s vira "offline", sem travar;
5. **teste do SmartScreen:** enviar o `.exe` para si (Drive), baixar de novo e abrir: anotar
   o aviso e o caminho "Mais informações → Executar assim mesmo";
6. Defender: se colocar em quarentena, registrar e cair no plano B (condição 7).

## 8. Entrega

1. PR com o código, CI verde.
2. Lucas: janela de saída 6, deploy do `resumo-api`, regra 443 por IP, `docker stats`
   conferindo memória da isca e do `resumo-api`.
3. Build do `.exe` e teste manual (seção 7).
4. Registro no DEPLOY (janela 6, comandos, `docker stats`) e no README (como baixar e
   usar, e o plano B `uv run honeyant-local`).

## 9. Condições do Lucas (07/11)

1. A chave de acesso nunca vai no `.exe` nem no repositório: config local no perfil do
   usuário ou pergunta na primeira execução. Só a CA pública vai embutida.
2. A chave privada da CA não vai para a EC2 nem para o repositório: fica no PC do Lucas, fora
   do repo (seção 3.2).
3. Sem alcançar a EC2, o app cai para o último resumo em cache, sem travar, mostrando
   "resumo de <data>, offline", com teste.
4. Tempo constante e 5 erros / 15 min no `resumo-api`.
5. TLS: CA própria + IP no SAN + TLS 1.2+; nada de `verify=False` nem `check_hostname=False`;
   teste com certificado de outro IP recusando.
6. ADR do empacotamento com versão fixada; instruções de teste do Defender e do SmartScreen;
   `uv run honeyant-local` documentado como plano B.
7. Se o `.exe` não estiver estável até 08/11 às 18h, ele sai do escopo e o plano B vira o
   principal.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Defender põe o `.exe` em quarentena (falso positivo comum em `--onefile`) | Teste no 08/11; plano B `uv run honeyant-local` |
| Rede da faculdade bloqueia a 443 de saída ou o IP muda | Offline com cache; cadastrar o IP da rede no dia |
| IP da EC2 muda | Novo certificado do servidor com a mesma CA + nova URL no build |
| Memória da t3.micro | `mem_limit: 128m` no `resumo-api`; `docker stats` depois do deploy |
| Prazo | Condição 7: o `.exe` sai do escopo se não estiver estável até as 18h |

## 11. Ajustes do Lucas na aprovação (07/11)

1. Depois de um 401, o app para de consultar, cai para o cache e mostra "chave de acesso
   inválida"; erro de rede usa recuo exponencial com teto; testes para os dois (seções 3.3,
   5 e 7).
2. O IP da EC2 não é segredo (seção 3.2). A EC2 tem IP elástico.
3. Certificado do servidor com 90 dias e renovação no DEPLOY (seção 3.1).
4. `resumo-api` como `10002` em 8443, compose `443:8443`, sem root nem capabilities extras
   (seção 3.1).
5. Painel do app só em `127.0.0.1`, porta ocupada com mensagem clara, navegador abre sozinho,
   teste do bind (seções 3.3 e 7).
6. `build/`, `dist/` e `*.spec` no `.gitignore`; o `.exe` nunca vai para o repositório nem para
   Releases.
7. Dívida técnica: a chave de acesso fica em `%APPDATA%` em texto; no futuro, proteger com
   DPAPI.

## 12. Ordem de implementação

1. `resumo-api` + deploy na EC2 (evidência de cloud primeiro);
2. cliente HTTPS com cache e fallback, e o painel ao vivo;
3. empacotamento com PyInstaller e roteiro do Defender/SmartScreen.

Se o tempo acabar, o item 3 é o primeiro a sair (condição 7).
