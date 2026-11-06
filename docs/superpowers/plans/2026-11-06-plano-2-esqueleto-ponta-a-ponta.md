# Plano 2 — Leitura `mode=ro` na EC2 e esqueleto ponta a ponta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provar que um segundo container lê o SQLite da isca em `mode=ro` na EC2 e colocar de pé, em `apps/local`, o caminho perfil → evidência de fixture → fuzzy → ACO → SSE → SVG simples, com um teste E2E mínimo verde.

**Architecture:** O `intel` ganha só um adaptador de leitura SQLite somente leitura, e `apps/verificar_ro.py` o usa num container com outro usuário, ao lado da isca. O `pathfinder` ganha um caso de uso (`prever_rota`) e um observador que coleta snapshots. O `painel` ganha uma app FastAPI mínima que recebe uma porta `FonteDoFormigueiro` e transmite snapshots por SSE para um SVG em JS puro. `apps/local.py` é o composition root que liga fixtures, pathfinder e painel. Nenhum módulo importa outro.

**Tech Stack:** Python 3.12, pydantic v2, numpy/scikit-fuzzy (extra `inteligencia`), FastAPI + uvicorn (novo extra `painel`), httpx (TestClient), SQLite WAL, Docker Compose, SVG + JavaScript puro com `EventSource`.

**Spec:** `docs/superpowers/specs/2026-11-05-arapuca-honeyant-design.md` (seções 3 "Isolamento na EC2", 4, 5, 8, 9, 11 "Transporte", 12 "Painel e API", 14, 17 "06/11 tarde")

## Estado em 06/11 (já feito)

- Contratos do `core` e fixtures em `docs/demo/` estão na `main`; o CI já falha se `docs/contratos/*.schema.json` estiver desatualizado (`tests/unit/core/test_esquemas.py`). **A exportação de JSON Schema no CI está feita**; este plano não mexe nela.
- O `pathfinder` na `main` já tem `fraqueza`, `ModeloDeRisco`, `montar_grafo`, `Dijkstra` e `ACO(parametros, observadores)` com `ObservadorDeIteracao.notificar(snapshot)`.
- Sobre as fixtures, o ACO (semente 42) e o Dijkstra coincidem: no perfil inseguro, `internet → camera → broker → fechadura` com custo ≈ **1,422**; no seguro, `internet → roteador → broker → fechadura` com custo ≈ **4,856**.
- Teste de captura (Plano 1, tarefa 11) feito.

## Global Constraints

- Tudo do Plano 1 continua valendo: Python 3.12, `uv.lock` commitado e `uv sync --locked` no CI, nomes em português sem acentos, **quem commita é o Lucas**, nunca `git add .`.
- A API do pathfinder usada aqui é a da **`main`** (`honeyant.pathfinder.aco.ACO`, `honeyant.pathfinder.grafo.montar_grafo`, `ObservadorDeIteracao.notificar`). A pasta `pathfinder/dominio/` das branches antigas do Kauã não é usada. O PR corrigido dele (`pathfinder/adapters/replay.py`, `GravadorDeReplay`) entra antes ou em paralelo; **este plano não cria gravador de replay**. O `ColetorDeSnapshots` só junta snapshots em memória para o SSE. Quando o replay for para o painel, ele usa o `GravadorDeReplay` do Kauã.
- Regra de dependência (import-linter): `intel`, `pathfinder` e `painel` importam só `core`; **só `apps/` monta mais de um módulo**.
- FastAPI e uvicorn ficam no extra **`painel`**, fora da imagem da isca; o grupo `dev` passa a puxar `honeyant[inteligencia,painel]` e `httpx`.
- SQLite somente leitura: URI `Path.resolve().as_uri() + "?mode=ro"` com `uri=True` (funciona no Windows e no Linux). O leitor **nunca cria** o arquivo do banco.
- O container de verificação roda como usuário **10002:10001** (outro usuário, mesmo grupo da isca), com `read_only: true`, `cap_drop: [ALL]` e `no-new-privileges`.
- SSE: `GET /api/v1/formigueiro/stream?modo=prever&semente=42&velocidade=1`, evento `snapshot`; **no máximo um snapshot a cada 150 ms**; `velocidade` em **[0,25; 4]**; intervalo entre snapshots = `max(0,15, 0,6 / velocidade)` s.
- O painel local escuta em **127.0.0.1:8000** por padrão. Autenticação e TLS **ficam para o plano do painel** (spec, seção 12); até lá ele nunca escuta em `0.0.0.0`.
- Front: CSP `default-src 'self'` sem `'unsafe-inline'`; nenhum `<script>` inline; texto de nó só por `textContent`, **nunca `innerHTML`**.
- Branches: Tarefas 1–2 em `feat/leitura-ro` (PR revisado pelo **Rafael**, dono do `intel`); Tarefas 3–6 em `feat/esqueleto-local` (PR revisado pelo **Gustavo**, que consome o pathfinder, e pelo **Kawe**, revisor do painel).

## Review Focus

1. **O leitor abre o banco antes de a isca ter criado o arquivo** → erro claro `FileNotFoundError`, sem criar um banco vazio que esconderia o problema. Teste na Tarefa 1.
2. **A isca grava enquanto o leitor lê (WAL, checkpoint)** → o leitor nunca vê `database is locked` e a contagem só cresce. Teste na Tarefa 1.
3. **Query do SSE malformada** (`velocidade=10`, `velocidade=abc`, `semente=-1`, `modo=xyz`) → 422, sem stack trace e sem começar o ACO. Teste na Tarefa 4.
4. **Casa sem caminho até a fechadura** (todas as arestas para o broker bloqueadas) → `prever_rota` devolve `None`, o stream termina normalmente com `melhor: null` e o painel mostra "sem rota". Testes nas Tarefas 3 e 4.
5. **Rótulo de nó com HTML** (`<img onerror=…>`) → aparece como texto. O JS nunca usa `innerHTML`, e o perfil é servido como JSON. Teste na Tarefa 6.

---

## Estrutura de arquivos

```
pyproject.toml                               # extra painel, httpx no dev, scripts novos
src/honeyant/intel/ports.py                  # FonteDeEventos (Protocol)
src/honeyant/intel/adapters/__init__.py
src/honeyant/intel/adapters/sqlite_leitura.py  # LeitorSqlite (mode=ro)
src/honeyant/apps/verificar_ro.py            # CLI honeyant-verificar-ro
infra/compose.verificar-ro.yml               # override: container leitor ao lado da isca
infra/aws/DEPLOY.md                          # + seção "Verificação do mode=ro"
src/honeyant/pathfinder/prever.py            # prever_rota, ColetorDeSnapshots
src/honeyant/painel/ports.py                 # FonteDoFormigueiro (Protocol)
src/honeyant/painel/app.py                   # criar_app(): perfil, SSE, estáticos, CSP
src/honeyant/painel/static/index.html
src/honeyant/painel/static/formigueiro.js
src/honeyant/apps/local.py                   # composition root local + CLI honeyant-local
tests/integration/test_leitura_ro.py
tests/unit/pathfinder/test_prever.py
tests/unit/painel/test_app.py
tests/unit/painel/test_static.py
tests/e2e/test_esqueleto.py
```

---

### Task 1: Leitor SQLite somente leitura (`intel`)

**Files:**
- Create: `src/honeyant/intel/ports.py`, `src/honeyant/intel/adapters/__init__.py`, `src/honeyant/intel/adapters/sqlite_leitura.py`
- Test: `tests/integration/test_leitura_ro.py`

**Interfaces:**
- Consumes: o esquema das tabelas `eventos` e `acumulado` de `honeyant.arapuca.adapters.sqlite`, **copiado como texto SQL**. O `intel` não importa o `arapuca`. O teste usa `RepositorioSqlite` para escrever, porque testes podem importar vários módulos.
- Produces:
  - `FonteDeEventos(Protocol)`: `contar() -> int`, `acumulado_por_servico() -> dict[Servico, int]`
  - `LeitorSqlite(caminho: Path)`: implementa `FonteDeEventos`, mais `modo() -> str` (sempre `"ro"`), `escrita_bloqueada() -> bool` e `fechar() -> None`. Levanta `FileNotFoundError` se o arquivo não existe.

- [ ] **Step 1: Escrever os testes que falham** em `tests/integration/test_leitura_ro.py`, sem o marcador `integration` (só usa arquivo local):

```python
def test_le_o_que_a_isca_gravou(tmp_path):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    repo.salvar(evento(Servico.TELNET)); repo.salvar(evento(Servico.MQTT))
    leitor = LeitorSqlite(tmp_path / "isca.db")
    assert leitor.contar() == 2
    assert leitor.acumulado_por_servico() == {Servico.TELNET: 1, Servico.MQTT: 1}

def test_escrita_e_recusada(tmp_path):
    RepositorioSqlite(tmp_path / "isca.db")
    assert LeitorSqlite(tmp_path / "isca.db").escrita_bloqueada() is True

def test_banco_inexistente_da_erro_claro_e_nao_cria_arquivo(tmp_path):
    with pytest.raises(FileNotFoundError):
        LeitorSqlite(tmp_path / "nao-existe.db")
    assert not (tmp_path / "nao-existe.db").exists()

def test_leitura_concorrente_com_escrita(tmp_path):
    # thread escreve 200 eventos; leitor conta 200 vezes
    # assert: nenhuma exceção; contagens em ordem não decrescente; última == 200
```

`evento(servico)` é um helper local que monta um `EventoDeAtaque` válido (copiar o padrão de `tests/unit/arapuca/test_repositorio.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/integration/test_leitura_ro.py -v`
Expected: FAIL com `ModuleNotFoundError: honeyant.intel.adapters`

- [ ] **Step 3: Implementar `LeitorSqlite` em `src/honeyant/intel/adapters/sqlite_leitura.py`**

Abre com `sqlite3.connect(caminho.resolve().as_uri() + "?mode=ro", uri=True)`, depois de checar `caminho.is_file()`, que levanta `FileNotFoundError` com o caminho na mensagem. `escrita_bloqueada()` tenta `CREATE TABLE _sonda (x)` e devolve `True` em `sqlite3.OperationalError` com "readonly" na mensagem. Se a escrita passar, faz rollback e devolve `False`. Docstring: o leitor nunca é o escritor e é aqui que o painel e o intel leem na EC2.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/integration/test_leitura_ro.py -v && uv run lint-imports`
Expected: 4 passed; contratos do import-linter KEPT

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/intel/ports.py src/honeyant/intel/adapters/__init__.py src/honeyant/intel/adapters/sqlite_leitura.py tests/integration/test_leitura_ro.py
git commit -m "feat(intel): adiciona leitor SQLite somente leitura (mode=ro)"
```

---

### Task 2: Verificação do `mode=ro` no compose real (local e EC2)

**Files:**
- Create: `src/honeyant/apps/verificar_ro.py`, `infra/compose.verificar-ro.yml`
- Modify: `pyproject.toml` (`[project.scripts]`: `honeyant-verificar-ro = "honeyant.apps.verificar_ro:main"`), `infra/aws/DEPLOY.md` (nova seção no fim)
- Test: `tests/unit/apps/test_verificar_ro.py`

**Interfaces:**
- Consumes: `LeitorSqlite` (Tarefa 1).
- Produces: `relatorio(caminho: Path) -> dict` com as chaves `modo`, `eventos`, `acumulado` (`servico → int`) e `escrita_bloqueada`; `main()` imprime esse dict em JSON numa linha e sai com **0** se `modo == "ro"` e `escrita_bloqueada`, senão **1**. O banco vem de `HONEYANT_DB` (padrão `/dados/isca.db`, o mesmo da isca).

- [ ] **Step 1: Teste que falha**: `test_relatorio_do_banco_da_isca(tmp_path)` grava 3 eventos com `RepositorioSqlite`. Assert: `relatorio(...) == {"modo": "ro", "eventos": 3, "acumulado": {...}, "escrita_bloqueada": True}`.

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/apps/test_verificar_ro.py -v` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar `relatorio` e `main` em `src/honeyant/apps/verificar_ro.py`**, sem IPs na saída.

- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → 1 passed.

- [ ] **Step 5: Escrever `infra/compose.verificar-ro.yml`**, um override de `infra/compose.cloud.yml` com o serviço `verificar-ro`: `image: honeyant-isca:local`, `user: "10002:10001"`, `command: ["honeyant-verificar-ro"]`, volume `dados:/dados` (com escrita, por causa dos arquivos `-wal`/`-shm`, como diz o spec), `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `restart: "no"`, `profiles: [verificacao]` (assim, `up -d` não o sobe).

- [x] **Step 6: Rodar localmente, com a isca de pé**

Run (Git Bash, na raiz):
```bash
docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml up -d --build isca
uv run python -c "import socket,time;s=socket.create_connection(('127.0.0.1',23));s.sendall(b'admin\r\nadmin\r\n');time.sleep(1);s.close()"
docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml run --rm verificar-ro
```
Expected: uma linha JSON com `"eventos" >= 1`, `"escrita_bloqueada": true` e `"arquivo_gravavel": false`, e saída com código 0. Se der `attempt to write a readonly database` ou `unable to open database file` **na leitura**, o leitor não conseguiu usar o `-shm` da isca: passe para o plano B do Step 8.

- [x] **Step 6b: Repetir com a isca parada** (`... stop isca`, depois `run --rm verificar-ro`). A isca, ao desligar limpa, apaga o `-wal`/`-shm`, e o leitor precisa recriá-los, o que depende do diretório 2775 do `init-dados`. Expected: igual ao Step 6. Depois, `... start isca`.

- [x] **Step 7: Rodar na EC2.** Primeiro `docker compose -f infra/compose.cloud.yml build isca`: a imagem antiga não tem o `honeyant-verificar-ro`, e o `build` só troca a imagem, sem recriar a isca que está no ar. Depois, `docker compose -f infra/compose.cloud.yml up -d init-dados` (aplica o 2775) e o mesmo `run --rm verificar-ro` do Step 6, sem enviar o login de teste, porque a isca já tem eventos reais. Abra a saída temporariamente só se o `--build` precisar baixar imagens (procedimento do `DEPLOY.md`). Expected: igual ao Step 6, com `eventos` no tamanho do que a isca coletou. Rode só o `run --rm verificar-ro`: o `up -d --build isca` recriaria a isca que está coletando.

- [x] **Step 8: Registrar o resultado** numa seção "Verificação do mode=ro" no `infra/aws/DEPLOY.md`: data, comando, saída (sem IPs) e conclusão. **Plano B, se falhar:** testar `user: "10002:10001"` com `group_add` e `umask 002` na isca. Se ainda falhar, seguir o spec: endpoint interno da isca, só na rede Docker. A decisão fica registrada no texto, e esse ajuste vira tarefa própria.

- [ ] **Step 9: Commit (Lucas)**

```powershell
git add src/honeyant/apps/verificar_ro.py tests/unit/apps/test_verificar_ro.py infra/compose.verificar-ro.yml infra/aws/DEPLOY.md pyproject.toml uv.lock
git commit -m "feat(apps): verifica a leitura mode=ro do banco da isca no compose real"
```

---

### Task 3: Caso de uso `prever_rota` e coletor de snapshots (`pathfinder`)

**Files:**
- Create: `src/honeyant/pathfinder/prever.py`
- Test: `tests/unit/pathfinder/test_prever.py`

**Interfaces:**
- Consumes: `montar_grafo`, `ModeloDeRisco`, `ACO`, `ParametrosACO`, `AlgoritmoDeRota`, `combinar_evidencias` (todos já na `main`).
- Produces:
  - `prever_rota(perfil: PerfilDaCasa, evidencias: Iterable[EvidenciaDeRede], resumo: ResumoDeAmeaca, algoritmo: AlgoritmoDeRota, modelo: ModeloDeRisco | None = None) -> Rota | None`: combina as evidências, monta o grafo e chama `algoritmo.calcular(grafo, perfil.origem, perfil.alvo)`.
  - `ColetorDeSnapshots`: `ObservadorDeIteracao` com o atributo `snapshots: list[Snapshot]`.

- [ ] **Step 1: Testes que falham**, carregando `docs/demo/` como em `tests/unit/core/test_fixtures_demo.py`:

```python
def test_inseguro_passa_pela_camera():
    rota = prever_rota(perfil("inseguro"), evid("inseguro"), resumo(), ACO())
    assert rota.nos == ["internet", "camera", "broker", "fechadura"]
    assert rota.custo == pytest.approx(1.422, abs=1e-3)

def test_mitigar_muda_a_rota_e_encarece():
    antes = prever_rota(perfil("inseguro"), evid("inseguro"), resumo(), ACO())
    depois = prever_rota(perfil("seguro"), evid("seguro"), resumo(), ACO())
    assert depois.nos == ["internet", "roteador", "broker", "fechadura"]
    assert depois.custo > antes.custo

def test_coletor_recebe_um_snapshot_por_iteracao():
    coletor = ColetorDeSnapshots()
    prever_rota(perfil("inseguro"), evid("inseguro"), resumo(),
                ACO(ParametrosACO(iteracoes=7), observadores=[coletor]))
    assert [s.iteracao for s in coletor.snapshots] == list(range(7))

def test_sem_caminho_ate_a_fechadura_devolve_none():
    # evidências do inseguro + alcancavel=False (fonte ativo, mais recente) em
    # todas as arestas *->broker
    assert prever_rota(perfil("inseguro"), bloqueadas, resumo(), ACO()) is None
    assert prever_rota(perfil("inseguro"), bloqueadas, resumo(), Dijkstra()) is None
```

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/pathfinder/test_prever.py -v` → FAIL (`honeyant.pathfinder.prever` inexistente).

- [ ] **Step 3: Implementar `src/honeyant/pathfinder/prever.py`.**

- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → 4 passed; depois `uv run pytest tests/unit/pathfinder -q` → todos verdes.

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/pathfinder/prever.py tests/unit/pathfinder/test_prever.py
git commit -m "feat(pathfinder): adiciona caso de uso prever_rota e coletor de snapshots"
```

---

### Task 4: Painel mínimo com SSE (`painel`)

**Files:**
- Modify: `pyproject.toml` (extra `painel = ["fastapi>=0.115", "uvicorn>=0.32"]`; `dev` com `honeyant[inteligencia,painel]` e `httpx`), `uv.lock`
- Create: `src/honeyant/painel/ports.py`, `src/honeyant/painel/app.py`, `src/honeyant/painel/static/index.html` (casca vazia; o conteúdo vem na Tarefa 6)
- Test: `tests/unit/painel/test_app.py`

**Interfaces:**
- Consumes: só `core` (`PerfilDaCasa`, `Snapshot`).
- Produces:
  - `FonteDoFormigueiro(Protocol)`: `snapshots(semente: int) -> Sequence[Snapshot]`
  - `criar_app(perfil: PerfilDaCasa, fonte: FonteDoFormigueiro, intervalo_base: float = 0.6, intervalo_minimo: float = 0.15, dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> FastAPI`, com as rotas:
    - `GET /api/v1/perfil` → `perfil.model_dump(mode="json")`
    - `GET /api/v1/formigueiro/stream?modo=prever&semente=42&velocidade=1` → `text/event-stream`. Cada snapshot sai como `event: snapshot\ndata: <Snapshot JSON>\n\n`; no fim, `event: fim\ndata: {}\n\n`. `modo: Literal["prever"]`, `semente: int = Query(42, ge=0, le=2**31 - 1)`, `velocidade: float = Query(1, ge=0.25, le=4)`. A espera entre eventos é `max(intervalo_minimo, intervalo_base / velocidade)`, com `asyncio.sleep`.
    - `GET /` e `/static/*` → arquivos de `painel/static/`
    - Middleware: em toda resposta, `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'` e `X-Content-Type-Options: nosniff`

- [ ] **Step 1: Dependências.** Rode `uv add --optional painel "fastapi>=0.115" "uvicorn>=0.32"` e `uv add --dev httpx`. Ajuste o `dev` para `honeyant[inteligencia,painel]`. Run: `uv sync && uv run python -c "import fastapi"` → sem erro.

- [ ] **Step 2: Testes que falham** em `tests/unit/painel/test_app.py`, com uma `FonteFalsa` que devolve 3 snapshots fixos (de `docs/demo/snapshots-exemplo.jsonl`) e registra as sementes pedidas. Use `criar_app(perfil, fonte, intervalo_base=0, intervalo_minimo=0)` e o `TestClient`. Um teste à parte, `test_intervalo_respeita_o_minimo`, injeta um `dormir` falso (parâmetro `dormir: Callable[[float], Awaitable[None]] = asyncio.sleep` de `criar_app`) e verifica as esperas `[0.15, 0.15]` para `velocidade=4` com os padrões, e `[0.6, 0.6]` para `velocidade=1`.

```python
def test_perfil_em_json(): ...  # status 200, json["perfil"] == "inseguro", 8 nós
def test_stream_entrega_snapshots_validos_e_fim():
    # eventos "snapshot" parseiam com Snapshot.model_validate_json; 3 deles; último evento é "fim"
def test_semente_chega_na_fonte(): ...  # ?semente=7 → fonte.sementes == [7]
@pytest.mark.parametrize("q", ["velocidade=10", "velocidade=0.1", "velocidade=abc",
                               "semente=-1", "modo=xyz"])
def test_query_invalida_da_422_sem_rodar_a_fonte(q): ...  # 422 e fonte.sementes == []
def test_snapshot_sem_rota_vai_como_null(): ...  # fonte com melhor=None → data tem "melhor": null
def test_csp_em_toda_resposta(): ...  # "/" e "/api/v1/perfil" com o header exato acima
```

- [ ] **Step 3: Rodar e ver falhar**: `uv run pytest tests/unit/painel -v` → FAIL (`honeyant.painel.app` inexistente).

- [ ] **Step 4: Implementar `ports.py` e `app.py`.** Use `StreamingResponse` de um gerador assíncrono. Os estáticos vêm de `Path(__file__).parent / "static"` via `StaticFiles`.

- [ ] **Step 5: Rodar e ver passar**: `uv run pytest tests/unit/painel -v && uv run lint-imports && uv run bandit -c pyproject.toml -r src` → tudo verde.

- [ ] **Step 6: Commit (Lucas)**

```powershell
git add pyproject.toml uv.lock src/honeyant/painel/ports.py src/honeyant/painel/app.py src/honeyant/painel/static/index.html tests/unit/painel/test_app.py
git commit -m "feat(painel): adiciona app minima com perfil e stream SSE do formigueiro"
```

---

### Task 5: Composition root local (`apps/local.py`) e E2E mínimo

**Files:**
- Create: `src/honeyant/apps/local.py`, `tests/e2e/test_esqueleto.py`
- Modify: `pyproject.toml` (`honeyant-local = "honeyant.apps.local:main"`; marcador `e2e` em `markers`)

**Interfaces:**
- Consumes: `prever_rota`, `ColetorDeSnapshots` (Tarefa 3); `criar_app`, `FonteDoFormigueiro` (Tarefa 4).
- Produces:
  - `ConfigLocal.de_ambiente(env: Mapping[str, str]) -> ConfigLocal`, com os campos `perfil: TipoDePerfil` (`HONEYANT_PERFIL`, padrão `inseguro`), `demo_dir: Path` (`HONEYANT_DEMO_DIR`, padrão `docs/demo`), `host: str` (`HONEYANT_HOST`, padrão `127.0.0.1`) e `porta: int` (`HONEYANT_PORTA`, padrão `8000`)
  - `FonteDasFixtures(perfil, evidencias, resumo)`: implementa `FonteDoFormigueiro`; `snapshots(semente)` roda `prever_rota` com `ACO(ParametrosACO(semente=semente), [coletor])` e devolve `coletor.snapshots`
  - `montar(config: ConfigLocal) -> FastAPI`: lê `perfil-<tipo>.json`, `evidencias-<tipo>.json` e `resumo-congelado.json` de `demo_dir`
  - `main()`: `uvicorn.run(montar(cfg), host=cfg.host, port=cfg.porta)`

- [ ] **Step 1: Testes que falham** em `tests/e2e/test_esqueleto.py` (`pytestmark = pytest.mark.e2e`; roda no CI, sem rede):

```python
def ultimo_snapshot(perfil):  # TestClient(montar(ConfigLocal(perfil=..., demo_dir=DEMO, ...)))
    # lê o stream com ?velocidade=4 e devolve o último Snapshot

def test_e2e_inseguro_rota_pela_camera():
    s = ultimo_snapshot("inseguro")
    assert s.iteracao == 49 and s.melhor.nos == ["internet", "camera", "broker", "fechadura"]

def test_e2e_mitigar_muda_rota_e_custo_sobe():
    antes, depois = ultimo_snapshot("inseguro"), ultimo_snapshot("seguro")
    assert "camera" not in depois.melhor.nos and depois.melhor.custo > antes.melhor.custo

def test_e2e_mesma_semente_mesmos_snapshots(): ...  # dois streams com semente=42 → listas iguais

def test_config_padrao_so_escuta_localhost():
    assert ConfigLocal.de_ambiente({}).host == "127.0.0.1"
```

Como 50 snapshots a 0,15 s levam 7,5 s por stream, `montar(config, intervalo_base=0.6, intervalo_minimo=0.15)` repassa os dois para `criar_app`, e o teste usa `0` nos dois.

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/e2e -v` → FAIL (`honeyant.apps.local` inexistente).

- [ ] **Step 3: Implementar `src/honeyant/apps/local.py`.**

- [ ] **Step 4: Rodar e ver passar**: `uv run pytest tests/e2e -v` → 4 passed; `uv run pytest -m "not integration" -q` → tudo verde.

- [ ] **Step 5: Subir de verdade**: `uv run honeyant-local` e, em outro terminal, `curl -N "http://127.0.0.1:8000/api/v1/formigueiro/stream?velocidade=4"`. Expected: eventos `snapshot` chegando aos poucos, terminando em `fim`.

- [ ] **Step 6: Commit (Lucas)**

```powershell
git add src/honeyant/apps/local.py tests/e2e/test_esqueleto.py pyproject.toml uv.lock
git commit -m "feat(apps): monta esqueleto local (fixtures, pathfinder e painel) com E2E minimo"
```

---

### Task 6: Formigueiro em SVG simples (`painel/static`)

**Files:**
- Modify: `src/honeyant/painel/static/index.html`
- Create: `src/honeyant/painel/static/formigueiro.js`
- Test: `tests/unit/painel/test_static.py`

**Interfaces:**
- Consumes: `GET /api/v1/perfil` e o stream SSE (Tarefa 4).
- Produces: a página `/`. O `index.html` tem `<svg id="formigueiro" viewBox="0 0 1000 600">`, `<p id="status">`, um controle de velocidade (`<select id="velocidade">` com 0.25, 0.5, 1, 2, 4), o botão `Prever invasão` e `<script src="/static/formigueiro.js" defer>`. O JS desenha um `<circle>` + `<text>` por nó, nas coordenadas `x, y` do perfil, e uma `<line>` por aresta. A cada `snapshot`, a espessura da linha vai de 1 a 12 px, proporcional ao feromônio normalizado pelo máximo do snapshot, e as arestas de `melhor` ficam com a classe `rota`, que muda cor **e** traço (cor não é o único canal). Com `melhor: null`, `#status` mostra "sem rota até a fechadura". No evento `fim`, `EventSource.close()`.

- [ ] **Step 1: Testes que falham** em `tests/unit/painel/test_static.py`:

```python
def test_html_sem_script_inline():
    # todo <script> do index.html tem src; nenhum atributo on*= no HTML
def test_js_nunca_usa_innerHTML_nem_eval():
    js = (STATIC / "formigueiro.js").read_text(encoding="utf-8")
    for proibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function"):
        assert proibido not in js
def test_rotulo_com_html_sai_como_json_escapado():
    # perfil com rotulo '<img src=x onerror=alert(1)>' → /api/v1/perfil é application/json
    # e o rótulo volta idêntico (o JS põe em textContent)
```

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/painel/test_static.py -v` → FAIL (`formigueiro.js` não existe).

- [ ] **Step 3: Implementar `index.html` e `formigueiro.js`.** JS puro, sem bibliotecas; elementos via `document.createElementNS("http://www.w3.org/2000/svg", ...)`; texto só com `textContent`. Os estilos vão num `<link rel="stylesheet">` ou em atributos SVG; `style` inline em HTML não entra, por causa da CSP.

- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → 3 passed.

- [x] **Step 5: Ver no navegador**: `uv run honeyant-local` → abrir `http://127.0.0.1:8000/` e clicar em "Prever invasão". Expected: oito nós, as linhas engrossam ao longo das iterações, a rota `internet → camera → broker → fechadura` fica destacada e o console não mostra erro de CSP. Repetir com `HONEYANT_PERFIL=seguro`: a rota passa pelo roteador e a ligação câmera→broker não aparece.

- [ ] **Step 6: Commit (Lucas)**

```powershell
git add src/honeyant/painel/static/index.html src/honeyant/painel/static/formigueiro.js tests/unit/painel/test_static.py
git commit -m "feat(painel): desenha o formigueiro em SVG simples a partir do stream"
```

---

## Fora deste plano (próximos planos)

- Painel: autenticação, bloqueio após 5 tentativas, TLS com CA própria, modos ao vivo e replay, formigueiro completo (Gustavo).
- `intel`: agregação real, `ResumoDeAmeaca` em `GET /api/v1/resumo` sobre o `LeitorSqlite` da Tarefa 1, fuzzy de intenção (Rafael).
- `twin`, `sensor` e `honeyant mitigar`/`verificar` reais, capturas `antes.pcap`/`depois.pcap` (Kawe e Rafael).
- `apps/nuvem.py` e `HONEYANT_APP=nuvem|local` na mesma imagem.
