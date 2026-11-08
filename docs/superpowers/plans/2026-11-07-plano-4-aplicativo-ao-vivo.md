# Plano 4 — Aplicativo HoneyAnt ao vivo (.exe)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um `HoneyAnt.exe` para Windows que abre o painel em `127.0.0.1` e mostra os ataques da isca ao vivo, buscando o resumo agregado num `resumo-api` novo na EC2, com fallback para cache e resumo embutido.

**Architecture:** Na EC2, um servidor HTTPS da biblioteca padrão (`intel/adapters/servidor_resumo.py`) serve só o `ResumoDeAmeaca` das últimas 24 h, com chave Bearer (hash scrypt), 5 erros/15 min e TLS da CA do projeto. No app, um adapter `FonteDoResumoAoVivo` (em `apps/`) implementa a porta `FonteDoResumo` do painel com três níveis (ao vivo → cache → embutido); o front passa a consultar o resumo a cada 15 s e solta uma formiga por ataque novo. O PyInstaller empacota tudo num `.exe`.

**Tech Stack:** Python 3.12 (`http.server`, `ssl`, `urllib`, `hashlib.scrypt`, `hmac`), FastAPI/uvicorn (já no extra `painel`), JS puro, `openssl` (geração de certificados), PyInstaller 6.22.3 (só no build).

**Spec:** `docs/superpowers/specs/2026-11-07-aplicativo-ao-vivo-design.md`

## Global Constraints

- Nenhuma dependência nova no projeto. PyInstaller só via `uv run --with pyinstaller==6.22.3`.
- `intel` não importa `painel` (import-linter): o hash da chave é implementado no `intel` no mesmo formato `scrypt$N$r$p$sal$hash` (N=16384, r=8, p=1, dklen=32, sal 16 bytes) do login.
- `resumo-api`: processo `10002:10001`, escuta **8443**, compose `443:8443`, `read_only`, `tmpfs /tmp`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit: 128m`, `pids_limit: 64`.
- Só `GET /api/v1/resumo`; o resto `404` vazio; cabeçalho `Server: honeyant`.
- Acesso: 5 erros por IP em 15 min → bloqueio de 15 min (`429`); comparação em tempo constante; sem `HONEYANT_RESUMO_CHAVE_HASH` o serviço não sobe.
- TLS: mínimo 1.2; cliente com CA própria, `check_hostname=True`, `CERT_REQUIRED`. Proibido no código: `verify=False`, `check_hostname = False`, `CERT_NONE`.
- Certificado do servidor: 90 dias, SAN `IP:<ip elástico>`. Chave da CA só em `%USERPROFILE%\.honeyant\ca\`.
- App: bind só em `127.0.0.1`, portas 8765–8774; mensagem quando todas ocupadas: "As portas 8765 a 8774 estão ocupadas. Feche outro HoneyAnt aberto e tente de novo."
- Cliente: timeout 5 s; intervalo 15 s; recuo exponencial 15→30→60… teto 300 s; depois de 401 não consulta mais; texto "chave de acesso inválida".
- Textos do cabeçalho: "Ao vivo · atualizado às HH:MM" / "Resumo de <data>, offline" / "Ataques reais, congelados em <data>" / "Dados de exemplo".
- Rota (Prever, Mitigar, Replay, "Antes e depois") sempre sobre o resumo embutido.
- Nada de segredo em commit; `infra/resumo-api.env`, `infra/certs-resumo/`, `infra/app/app-local.json`, `build/`, `dist/`, `*.spec` no `.gitignore`.
- Sem `Co-Authored-By` nem atribuição ao Claude.

## Review Focus

1. **Banco indisponível no `resumo-api`** (isca reiniciando, `-shm` ausente): responder `503` vazio, sem derrubar o processo → teste na Task 2.
2. **Cache corrompido ou gravado pela metade** (app fechado no meio da escrita): gravação atômica e cache inválido ignorado (cai no embutido) → teste na Task 4.
3. **Chave colada com espaço ou quebra de linha** no prompt do app: removidos nas pontas antes de salvar → teste na Task 6.
4. **Requisição lenta ou enorme no `resumo-api`** (cliente que abre e não manda nada): timeout de 10 s por conexão e corpo ignorado → teste na Task 2.
5. **Horário mostrado em UTC** em vez do horário local no "atualizado às HH:MM" → teste JS na Task 5.

---

## Parte 1 — `resumo-api` na EC2 (evidência de cloud)

### Task 1: Acesso por chave (hash, tempo constante, bloqueio)

**Files:**
- Create: `src/honeyant/intel/acesso.py`, `src/honeyant/apps/chave_app.py`, `tests/unit/intel/test_acesso.py`
- Modify: `pyproject.toml` (`honeyant-chave-app = "honeyant.apps.chave_app:main"`)

**Interfaces:**
- Produces:
  - `gerar_hash(chave: str, *, sal: bytes | None = None) -> str` e `hash_valido(salvo: str) -> bool` (formato do login);
  - `class ControleDeAcesso(hash_salvo: str, limite: int = 5, janela_s: float = 900, bloqueio_s: float = 900, relogio: Callable[[], float] = time.monotonic)` com `verificar(ip: str, cabecalho_authorization: str | None) -> Literal["ok", "negado", "bloqueado"]`;
  - `honeyant-chave-app`: imprime a chave nova (`secrets.token_urlsafe(32)`) e a linha `HONEYANT_RESUMO_CHAVE_HASH=<hash>`.

- [ ] **Step 1: Testes que falham** em `test_acesso.py`:
  - `test_chave_certa_ok`, `test_sem_cabecalho_negado`, `test_bearer_malformado_negado` (`"Basic x"`, `"Bearer"`, `""`);
  - `test_quinto_erro_bloqueia_por_15_min`: relógio falso; 5 `negado` → 6ª chamada (mesmo com a chave certa) `bloqueado`; avança 899 s → `bloqueado`; avança 901 s → `ok`;
  - `test_erros_de_outro_ip_nao_bloqueiam`;
  - `test_erros_fora_da_janela_nao_somam` (4 erros, avança 901 s, mais 4 → ainda não bloqueia);
  - `test_compara_em_tempo_constante`: `monkeypatch` de `hmac.compare_digest` registra a chamada;
  - `test_hash_valido` (aceita o gerado, recusa `"x"`, `"bcrypt$…"`);
  - `test_chave_app_imprime_chave_e_hash_que_confere` (capsys; o hash impresso valida a chave impressa).
- [ ] **Step 2:** `uv run pytest tests/unit/intel/test_acesso.py -q` → FAIL.
- [ ] **Step 3: Implementar.** `verificar` calcula o scrypt da chave recebida e compara com `hmac.compare_digest`; nunca registra a chave.
- [ ] **Step 4:** mesmo comando → PASS.
- [ ] **Step 5: Commit** `feat(intel): chave de acesso do resumo-api com hash scrypt e bloqueio por IP`.

### Task 2: Servidor HTTPS do resumo e comando `honeyant-servir-resumo`

**Files:**
- Create: `src/honeyant/intel/adapters/servidor_resumo.py`, `src/honeyant/apps/servir_resumo.py`, `tests/unit/intel/test_servidor_resumo.py`
- Modify: `pyproject.toml` (`honeyant-servir-resumo = "honeyant.apps.servir_resumo:main"`)

**Interfaces:**
- Consumes: `ControleDeAcesso` (Task 1), `agregar` e `LeitorSqlite.eventos_desde`/`acumulado_por_servico` (intel).
- Produces:
  - `criar_servidor(endereco: str, porta: int, fonte: Callable[[], ResumoDeAmeaca], acesso: ControleDeAcesso, contexto_tls: ssl.SSLContext | None, cache_s: float = 15, relogio=time.monotonic) -> ThreadingHTTPServer` (`contexto_tls=None` só nos testes);
  - `contexto_servidor(cert: Path, chave: Path) -> ssl.SSLContext` (`minimum_version=TLSv1_2`);
  - `honeyant-servir-resumo`: lê `HONEYANT_DB` (padrão `/dados/isca.db`), `HONEYANT_RESUMO_CHAVE_HASH`, `HONEYANT_RESUMO_CERT`, `HONEYANT_RESUMO_CERT_CHAVE`; escuta `0.0.0.0:8443`.

- [ ] **Step 1: Testes que falham** (servidor sem TLS numa porta livre, `urllib` real):
  - `test_resumo_com_chave_certa_200_sem_ipv4` (JSON valida em `ResumoDeAmeaca`; regex de IPv4 não casa);
  - `test_sem_chave_401_e_bloqueio_429` (5×401 → 429);
  - `test_outra_rota_e_outro_metodo_404_vazio` (`/`, `/api/v1/casa`, `POST /api/v1/resumo`): corpo vazio e `Server: honeyant`;
  - `test_cache_de_15_s` (fonte conta as chamadas; 3 requisições → 1 chamada; relógio +16 s → 2);
  - `test_banco_indisponivel_503` (fonte levanta `sqlite3.OperationalError` → 503 vazio; a requisição seguinte com a fonte ok → 200) — Review Focus 1;
  - `test_conexao_lenta_fecha_em_10_s` (socket que conecta e não manda nada é fechado; usar `timeout` do handler, testado com valor reduzido por parâmetro) — Review Focus 4;
  - `test_main_sem_hash_recusa_subir` (`SystemExit` diferente de 0 e mensagem citando `honeyant-chave-app`);
  - `test_log_nunca_tem_a_chave` (caplog/capsys sem a chave nem `Authorization`).
- [ ] **Step 2:** `uv run pytest tests/unit/intel/test_servidor_resumo.py -q` → FAIL.
- [ ] **Step 3: Implementar.** `BaseHTTPRequestHandler` com `server_version = "honeyant"`, `sys_version = ""`, `timeout = 10`; `log_message` sobrescrito para uma linha JSON (`status`, `rota`, `ms`). IP do cliente: `self.client_address[0]`.
- [ ] **Step 4:** mesmo comando → PASS; `uv run lint-imports` → 3 contratos ok.
- [ ] **Step 5: Commit** `feat(intel): resumo-api so com GET /api/v1/resumo, chave Bearer e cache de 15 s`.

### Task 3: Certificados, compose e DEPLOY (TLS real)

**Files:**
- Create: `src/honeyant/apps/certificados.py`, `src/honeyant/apps/resumo_ao_vivo.py` (só `contexto_cliente` nesta task), `tests/integration/test_tls_resumo.py`
- Modify: `infra/compose.cloud.yml` (serviço `resumo-api`), `.gitignore`, `infra/aws/DEPLOY.md` (seção 7.2 "resumo-api": gerar chave e certificados, `scp`, permissões, deploy, `docker stats`, renovação de 90 dias), `pyproject.toml` (`honeyant-certificados = "honeyant.apps.certificados:main"`)

**Interfaces:**
- Consumes: `contexto_servidor`, `criar_servidor` (Task 2).
- Produces:
  - `honeyant-certificados --ip <ip> [--ca-dir ~/.honeyant/ca] [--saida infra/certs-resumo]`: cria a CA (se não existir; `ca.key` + `ca.crt`, 5 anos) e emite `servidor.crt`/`servidor.key` com 90 dias e `subjectAltName=IP:<ip>` usando o `openssl` do PATH; erro claro se não houver `openssl`;
  - `contexto_cliente(ca: Path) -> ssl.SSLContext` em `src/honeyant/apps/resumo_ao_vivo.py` (criado aqui, usado na Task 4).

- [ ] **Step 1: Testes que falham** (`tests/integration/test_tls_resumo.py`, `pytest.mark.skipif(shutil.which("openssl") is None)`, **sem** marca `integration` para rodar no CI):
  - `test_ca_certa_e_ip_certo_conecta` (certificado para `127.0.0.1`, servidor real com TLS);
  - `test_certificado_de_outro_ip_recusa` (emitido para `10.9.8.7`; `ssl.SSLCertVerificationError`);
  - `test_certificado_de_outra_ca_recusa`;
  - `test_tls_1_1_recusado` (servidor com `maximum_version=TLSv1_1`; o cliente falha);
  - `test_certificado_tem_90_dias` (`openssl x509 -noout -enddate` do `servidor.crt` dá entre 89 e 90 dias a partir de hoje);
  - `test_chave_da_ca_fica_so_no_ca_dir` (a pasta de saída não contém `ca.key`).
- [ ] **Step 2:** `uv run pytest tests/integration/test_tls_resumo.py -q` → FAIL.
- [ ] **Step 3: Implementar** `certificados.py` e `contexto_cliente`. Compose: serviço `resumo-api` com as restrições das Global Constraints, `env_file: resumo-api.env`, volumes `dados:/dados` e `./certs-resumo:/certs:ro`, `HONEYANT_RESUMO_CERT=/certs/servidor.crt`. `.gitignore`: as entradas das Global Constraints. DEPLOY 7.2: `chown 10002:10001` e `chmod 600` em `resumo-api.env` e `servidor.key`; `ls -l` para conferir; regra de **entrada TCP 443** no Security Group só para os IPs cadastrados (equipe; a rede da banca no dia); `docker stats --no-stream` (isca e `resumo-api` abaixo dos limites); renovação: rodar `honeyant-certificados --ip <ip>` de novo, `scp`, `docker compose … restart resumo-api`.
- [ ] **Step 4:** mesmo comando → PASS; `uv run pytest -m "not integration" -q` → verde; teste de varredura (Task 4, Step 1, último item) ainda não existe — ok.
- [ ] **Step 5: Commit** `feat(infra): resumo-api no compose da nuvem, certificados de 90 dias e deploy documentado`.
- [ ] **Step 6: Pausa para o Lucas:** PR com CI verde → merge → comandos da janela 6 (DEPLOY 7.2) → Lucas confirma `curl` ao `resumo-api` com a chave (200), sem chave (401) e `docker stats`.

---

## Parte 2 — Cliente com cache e fallback, painel ao vivo

### Task 4: `FonteDoResumoAoVivo` (ao vivo → cache → embutido)

**Files:**
- Modify: `src/honeyant/apps/resumo_ao_vivo.py` (criado na Task 3), `src/honeyant/painel/modelos.py`
- Create: `tests/unit/apps/test_resumo_ao_vivo.py`, `tests/security/test_tls_no_codigo.py`

**Interfaces:**
- Consumes: `contexto_cliente` (Task 3), `FonteDoResumoLocal` (local.py), porta `FonteDoResumo`.
- Produces:
  - `ResumoComOrigem.origem: Literal["ao_vivo", "offline", "real", "exemplo"]`, `atualizado_em: datetime | None = None`, `aviso: str | None = None`;
  - `class ClienteResumo(url: str, chave: str, contexto: ssl.SSLContext, timeout_s: float = 5)` com `buscar() -> ResumoDeAmeaca`, levantando `ChaveInvalida`, `FalhaDeRede`, `RespostaInvalida`;
  - `class FonteDoResumoAoVivo(cliente: ClienteResumo | None, cache: Path, embutido: FonteDoResumo, relogio=time.monotonic, agora=lambda: datetime.now(UTC))` com `resumo() -> ResumoComOrigem`.

- [ ] **Step 1: Testes que falham** (cliente falso injetado; um servidor HTTP local para os de rede):
  - `test_sucesso_e_ao_vivo_e_grava_cache`;
  - `test_falha_de_rede_usa_cache_offline` (`origem == "offline"`, `atualizado_em` = do cache);
  - `test_sem_cache_usa_embutido`;
  - `test_401_para_de_consultar` (servidor conta: 1 chamada; mais 5 `resumo()` com o relógio andando → continua 1; `aviso == "chave de acesso inválida"`);
  - `test_recuo_exponencial_com_teto` (tempos de nova tentativa 15, 30, 60, 120, 240, 300, 300; sucesso volta a 15);
  - `test_servidor_que_nao_responde_nao_trava` (`resumo()` volta em < 6 s);
  - `test_resposta_invalida_descartada`;
  - `test_cache_corrompido_e_ignorado` e `test_cache_gravado_de_forma_atomica` (temporário + `os.replace`) — Review Focus 2;
  - `test_sem_chave_fica_offline_sem_rede` (`cliente=None`);
  - `tests/security/test_tls_no_codigo.py`: nenhum `.py` em `src/` contém `verify=False`, `check_hostname = False` nem `CERT_NONE`.
- [ ] **Step 2:** `uv run pytest tests/unit/apps/test_resumo_ao_vivo.py tests/security/test_tls_no_codigo.py -q` → FAIL.
- [ ] **Step 3: Implementar.** `ClienteResumo` com `urllib.request` + `HTTPSHandler(context=...)`; 401/403 → `ChaveInvalida`; timeout/conexão/TLS → `FalhaDeRede`; JSON que não valida → `RespostaInvalida`.
- [ ] **Step 4:** mesmo comando → PASS; `uv run pytest -m "not integration" -q` → verde.
- [ ] **Step 5: Commit** `feat(apps): fonte do resumo ao vivo com cache, recuo e parada no 401`.

### Task 5: Painel ao vivo (atualização a cada 15 s e uma formiga por ataque novo)

**Files:**
- Create: `src/honeyant/painel/static/js/aovivo.js`, `tests/js/aovivo.test.mjs`
- Modify: `src/honeyant/painel/static/js/app.js`, `src/honeyant/apps/local.py` (`montar(..., fonte_resumo: FonteDoResumo | None = None)`: a rota continua com o resumo embutido de `carregar_fontes`)

**Interfaces:**
- Consumes: `ResumoComOrigem` com `origem`, `atualizado_em`, `aviso` (Task 4); `cena.soltarAtaque(servico)`.
- Produces:
  - `textoDaOrigem(resumoComOrigem, fuso?) -> string` (os 4 textos das Global Constraints; "· chave de acesso inválida" anexado quando há `aviso`);
  - `novosAtaques(anterior: object|null, atual: object, maximo = 6) -> string[]` (lista de serviços, um por incremento; `anterior` nulo → `[]`).

- [ ] **Step 1: Testes que falham** (`aovivo.test.mjs`):
  - `novosAtaques({telnet: 10, mqtt: 1}, {telnet: 12, mqtt: 2})` → `["mqtt", "telnet", "telnet"]` (ordem alfabética);
  - teto: `{telnet: 0}` → `{telnet: 50}` → 6 itens; `anterior = null` → `[]`; contador que diminui → `[]`;
  - `textoDaOrigem` para as 4 origens; `"2026-11-08T15:04:00Z"` com fuso `America/Sao_Paulo` → `"Ao vivo · atualizado às 12:04"` — Review Focus 5;
  - com `aviso` → contém `"chave de acesso inválida"`.
- [ ] **Step 2:** `node --test tests/js/*.test.mjs` → FAIL.
- [ ] **Step 3: Implementar.** `app.js`: `setInterval` de 15 s chama `/api/v1/resumo`, atualiza o cabeçalho e o cartão "Ataques reais"; com `origem === "ao_vivo"`, solta `novosAtaques(...)` via `cena.soltarAtaque` e **desliga** o ritmo fixo de 2 s; fora do ao vivo mantém o ritmo fixo; nada com "reduzir movimento".
- [ ] **Step 4:** `node --test tests/js/*.test.mjs && uv run pytest -m "not integration" -q` → verde.
- [ ] **Step 5: Verificação no navegador** (Playwright + Edge): com uma `FonteDoResumo` falsa cujo acumulado sobe, as formigas aparecem e o cabeçalho diz "Ao vivo"; com ela falhando, "offline"; sem erros no console.
- [ ] **Step 6: Commit** `feat(painel): resumo ao vivo a cada 15 s e uma formiga por ataque novo`.

---

## Parte 3 — Empacotamento (sai primeiro se faltar tempo)

### Task 6: Comando `honeyant-app` (porta local, chave, navegador)

**Files:**
- Create: `src/honeyant/apps/aplicativo.py`, `tests/unit/apps/test_aplicativo.py`
- Modify: `pyproject.toml` (`honeyant-app = "honeyant.apps.aplicativo:main"`)

**Interfaces:**
- Consumes: `montar` (Task 5), `FonteDoResumoAoVivo`, `ClienteResumo`, `contexto_cliente`.
- Produces:
  - `recursos() -> Path` (`sys._MEIPASS` empacotado; raiz do repositório no desenvolvimento);
  - `abrir_socket(inicio: int = 8765, tentativas: int = 10) -> socket.socket` (bind em `127.0.0.1`; `PortasOcupadas` com a mensagem das Global Constraints);
  - `ler_chave(config: Path, perguntar: Callable[[str], str] = input) -> str | None` (lê `config.json`; sem chave ou JSON corrompido pergunta; salva `strip()`; vazio → `None`);
  - `main()`: monta o app com `FonteDoResumoAoVivo`, sobe `uvicorn.Server(...).run(sockets=[sock])`, abre o navegador com `webbrowser.open` depois de subir.

- [ ] **Step 1: Testes que falham:**
  - `test_bind_so_em_127_0_0_1` (`sock.getsockname()[0] == "127.0.0.1"`);
  - `test_porta_ocupada_usa_a_proxima`;
  - `test_todas_ocupadas_mensagem_clara` (ocupa 8765–8774 com sockets do teste; a mensagem exata);
  - `test_chave_colada_com_espacos_e_quebra_de_linha` → salva sem eles — Review Focus 3;
  - `test_config_corrompido_pergunta_de_novo`; `test_enter_vazio_fica_sem_chave`;
  - `test_recursos_em_desenvolvimento_aponta_para_docs_demo`.
- [ ] **Step 2:** `uv run pytest tests/unit/apps/test_aplicativo.py -q` → FAIL.
- [ ] **Step 3: Implementar.** `config.json` em `%APPDATA%\HoneyAnt\` (ou `~/.config/honeyant` fora do Windows); URL lida de `recursos()/app.json`; CA de `recursos()/ca.crt`.
- [ ] **Step 4:** mesmo comando → PASS.
- [ ] **Step 5: Commit** `feat(apps): honeyant-app sobe o painel em 127.0.0.1 com o resumo ao vivo`.

### Task 7: Build do `.exe`, ADR 0011, README e roteiro do Defender/SmartScreen

**Files:**
- Create: `infra/app/construir.ps1`, `infra/app/app-local.exemplo.json` (`{"url": "https://<ip-elastico>"}`), `docs/adr/0011-empacotamento-pyinstaller.md`
- Modify: `README.md` (seção "Aplicativo ao vivo": baixar, primeira execução, chave, SmartScreen, **plano B `uv run honeyant-local`**; dívida técnica: chave em `%APPDATA%` em texto, futuro DPAPI)

**Interfaces:**
- Consumes: `honeyant-app` (Task 6).
- Produces: `dist/HoneyAnt.exe` (fora do git).

- [ ] **Step 1:** `construir.ps1`: copia `infra/app/app-local.json` → `build-app/app.json` e `%USERPROFILE%\.honeyant\ca\ca.crt` → `build-app/ca.crt`; para se algum faltar; roda `uv run --with pyinstaller==6.22.3 pyinstaller --onefile --console --name HoneyAnt --add-data "docs/demo;docs/demo" --add-data "src/honeyant/painel/static;honeyant/painel/static" --add-data "src/honeyant/painel/login;honeyant/painel/login" --add-data "build-app/app.json;." --add-data "build-app/ca.crt;." src/honeyant/apps/aplicativo.py`.
- [ ] **Step 2:** rodar o script → `dist/HoneyAnt.exe` existe; `git status` não lista `build/`, `dist/`, `build-app/` nem `*.spec`.
- [ ] **Step 3: Teste manual** (spec, seção 7): abrir o `.exe` local; sem chave → "offline"; com chave e IP liberado → "Ao vivo"; sem internet → "offline" em até 20 s; enviar pelo Drive, baixar e abrir (SmartScreen: "Mais informações → Executar assim mesmo"); anotar se o Defender colocar em quarentena.
- [ ] **Step 4:** ADR 0011 (PyInstaller 6.22.3 vs Nuitka/zipapp; `--onefile`; falsos positivos; sem assinatura; plano B) e README.
- [ ] **Step 5: Commit** `feat(app): build do HoneyAnt.exe com PyInstaller 6.22.3 e roteiro do SmartScreen`.
- [ ] **Step 6: Critério de saída (condição 7):** se o Step 3 falhar até 08/11 às 18h, reverter só a Task 7 do escopo da entrega e deixar o README com o plano B como principal.
