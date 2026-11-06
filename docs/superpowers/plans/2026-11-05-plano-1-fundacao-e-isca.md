# Plano 1 — Fundação do repositório e isca na nuvem

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o repositório pronto para 5 pessoas trabalharem (pacote, lint, testes, regra de dependência e CI) e colocar a isca Telnet/MQTT no ar na EC2 hoje, registrando ataques reais.

**Architecture:** Um pacote Python `honeyant` (layout `src/`) com um subpacote por módulo. Neste plano só `core` (contrato `EventoDeAtaque`), `arapuca` (serviços falsos como Strategy, limites, repositório SQLite) e `apps/isca.py` (composition root da isca) ganham código. A isca roda num container sem privilégios na EC2, com saída de rede bloqueada no Security Group.

**Tech Stack:** Python 3.12, uv (dependências e `uv.lock`), pydantic v2, maxminddb, pytest + pytest-asyncio, ruff, import-linter, bandit, pip-audit, gitleaks, GitHub Actions, Docker/Compose, AWS EC2.

**Spec:** `docs/superpowers/specs/2026-11-05-arapuca-honeyant-design.md` (seções 3, 4, 5 "Isca", 6 `EventoDeAtaque`, 12, 15)

## Estado da infraestrutura (já feito pelo Lucas em 05/11)

- EC2 t3.micro em us-east-1, com Docker e Compose instalados, 2 GB de swap, 12 GB de disco e **saída bloqueada**; janela de saída documentada. O IP público **não** é versionado.
- Conta AWS nova, no plano pago básico; custo previsto de R$ 20–50 até a apresentação.
- Ruleset da `main` com 1 aprovação obrigatória e bypass para o admin.
- Wireshark instalado no notebook.

## Global Constraints

- Python **3.12** em todo lugar: `requires-python = ">=3.12,<3.13"`, `.python-version` = `3.12`, imagem `python:3.12-slim`. (A máquina do Lucas tem 3.14; o uv instala o 3.12.)
- Dependências fixadas pelo `uv.lock`, sempre commitado; CI usa `uv sync --locked`.
- Nomes de domínio, testes e mensagens em **português**, sem acentos em identificadores (`servico`, `usuario`).
- **Quem commita é o Lucas**, pelo PowerShell. Cada passo "Commit" lista os arquivos exatos; nunca `git add .`. Nenhum documento é commitado sem perguntar se pode ir ao repositório público.
- Trabalho em branch e PR: Tarefas 1–2 na branch `feat/fundacao` (PR revisado por qualquer integrante); Tarefas 3–10 na branch `feat/arapuca` (PR revisado pelo **Rafael**).
- Regra de dependência: `core` não importa nada do projeto; módulos importam só `core`; só `apps/` importa vários módulos.
- Isca: **nunca executa nada**; não abre conexões de saída; toda entrada é hostil.
- Limites da isca (decididos neste plano; o spec fixa só o teto): conexões simultâneas **200** no total e **4** por IP; **20** novas conexões por IP por minuto; **8192** bytes lidos por sessão; **15 s** de inatividade; **60 s** por sessão; **20** comandos por sessão.
- Armazenamento: retenção de **7 dias**; teto de **200.000 eventos** ou **200 MB**, descartando os mais antigos; contador acumulado por serviço nunca é apagado.
- Campos: `usuario`/`senha` até **64** caracteres; `comandos` até **20** itens de **256** caracteres.
- Portas: dentro do container **2323** (Telnet) e **18830** (MQTT); publicadas na EC2 como **23** e **1883**.
- Atribuição obrigatória: "IP Geolocation by DB-IP (https://db-ip.com)", licença CC-BY 4.0, no README.

## Review Focus

1. **Bytes binários, negociação Telnet (IAC) e UTF-8 inválido** → evento salvo com texto substituído, sem exceção nem sessão travada. Teste na Tarefa 6.
2. **Cliente que conecta e não envia nada** (estilo slowloris) → sessão encerrada em 15 s e vaga liberada no limitador. Teste na Tarefa 8.
3. **MQTT com "remaining length" mentiroso** (varint com mais de 4 bytes, ou valor maior que o limite) → sessão encerrada sem ler além do limite. Teste na Tarefa 7.
4. **IPv4 mapeado em IPv6** (`::ffff:1.2.3.4`, comum no Docker) → gravado como `1.2.3.4`, para que limites e geo tratem o mesmo IP do mesmo jeito. Teste na Tarefa 3.
5. **Reinício do container** → contador acumulado e eventos preservados ao reabrir o banco. Teste na Tarefa 4.

---

## Estrutura de arquivos

```
pyproject.toml                      # pacote, deps, ruff, pytest, bandit, import-linter
uv.lock  .python-version
LICENSE  README.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md
.github/workflows/ci.yml
src/honeyant/__init__.py
src/honeyant/{core,arapuca,intel,twin,sensor,pathfinder,painel,apps}/__init__.py
src/honeyant/core/texto.py          # limpar(): remove controles e trunca
src/honeyant/core/eventos.py        # Servico, EventoDeAtaque
src/honeyant/arapuca/ports.py       # RepositorioDeEventos, ResolvedorGeo, ServicoFalso, Captura
src/honeyant/arapuca/leitor.py      # LeitorLimitado, LimiteExcedido
src/honeyant/arapuca/limites.py     # Limitador (conexões e taxa por IP)
src/honeyant/arapuca/telnet.py      # remover_iac(), ServicoTelnet
src/honeyant/arapuca/mqtt.py        # ler_varint(), ServicoMqtt
src/honeyant/arapuca/servidor.py    # ServidorDaIsca (asyncio)
src/honeyant/arapuca/adapters/sqlite.py   # RepositorioSqlite
src/honeyant/arapuca/adapters/memoria.py  # RepositorioEmMemoria
src/honeyant/arapuca/adapters/geo.py      # GeoDbIp, GeoNulo
src/honeyant/apps/isca.py           # composition root + CLI (servir, estatisticas)
infra/docker/Dockerfile.isca
infra/compose.cloud.yml
infra/scripts/baixar-dbip.sh
infra/aws/DEPLOY.md
infra/teste-captura/{compose.yml,mosquitto.conf}
docs/adr/0004-isca-baixa-interacao.md
tests/unit/...  tests/integration/...  tests/security/...
```

---

### Task 1: Esqueleto do pacote e arquivos de comunidade

**Files:**
- Create: `pyproject.toml`, `.python-version`, `LICENSE`, `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- Create: `src/honeyant/__init__.py` e `__init__.py` vazio em `core`, `arapuca`, `arapuca/adapters`, `intel`, `twin`, `sensor`, `pathfinder`, `painel`, `apps`
- Test: `tests/unit/test_pacote.py`

**Interfaces:**
- Produces: pacote importável `honeyant` com `honeyant.__version__ = "0.1.0"`; comandos `uv run pytest`, `uv run ruff check`.

- [ ] **Step 1: Criar o ambiente**

Run (PowerShell, na raiz): `uv python install 3.12` e depois `uv init --lib --name honeyant --python 3.12 .` (se o uv recusar por já existir conteúdo, criar o `pyproject.toml` à mão com build backend `hatchling` e `packages = ["src/honeyant"]`).
Expected: `.python-version` contém `3.12`.

- [ ] **Step 2: Configurar `pyproject.toml`**

- `[project]`: `name = "honeyant"`, `version = "0.1.0"`, `requires-python = ">=3.12,<3.13"`, `license = "MIT"`, `dependencies = ["pydantic>=2", "maxminddb>=2"]`.
- Grupo dev (`uv add --dev`): `pytest`, `pytest-asyncio`, `ruff`, `import-linter`, `bandit[toml]`.
- `[tool.ruff]`: `line-length = 100`, `target-version = "py312"`; `[tool.ruff.lint] select = ["E","F","W","I","B","UP","S","ASYNC"]`; `per-file-ignores = {"tests/**" = ["S101"]}`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`, `markers = ["integration: precisa de rede local ou docker"]`.
- `[tool.bandit]`: `exclude_dirs = ["tests"]`.

- [ ] **Step 3: Escrever o teste**

```python
# tests/unit/test_pacote.py
import importlib

MODULOS = ["core", "arapuca", "intel", "twin", "sensor", "pathfinder", "painel", "apps"]

def test_pacote_tem_versao():
    import honeyant
    assert honeyant.__version__ == "0.1.0"

def test_todos_os_modulos_importam():
    for nome in MODULOS:
        importlib.import_module(f"honeyant.{nome}")
```

- [ ] **Step 4: Rodar o teste**

Run: `uv run pytest tests/unit/test_pacote.py -v`
Expected: 2 passed

- [ ] **Step 5: Arquivos de comunidade**

- `LICENSE`: texto MIT padrão, `Copyright (c) 2026 Equipe Arapuca HoneyAnt`.
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1 em português, com contato = e-mail do repositório definido pelo Lucas (perguntar; não usar e-mail pessoal sem autorização).
- `CONTRIBUTING.md`: como instalar (`uv sync`), como rodar os testes e o lint, fluxo "uma branch por tarefa → PR → revisão do consumidor (tabela da seção 16 do spec) → CI verde → merge", padrão de mensagem `tipo: descrição` em português.
- `README.md`: o que é (frase-guia do spec), status "em construção", como rodar os testes, licença, e a seção "Atribuições" com o texto do DB-IP das Global Constraints.

- [ ] **Step 6: Verificar o lint**

Run: `uv run ruff check . ; uv run ruff format --check .`
Expected: `All checks passed!` e nenhum arquivo a formatar.

- [x] **Step 7: Commit (Lucas)** ✅ 06/11 — antes, Claude pergunta se README/CONTRIBUTING/CODE_OF_CONDUCT podem ir ao público.

```powershell
git switch -c feat/fundacao
git add pyproject.toml uv.lock .python-version LICENSE README.md CONTRIBUTING.md CODE_OF_CONDUCT.md src/honeyant tests/unit/test_pacote.py
git commit -m "chore: cria esqueleto do pacote honeyant e arquivos de comunidade"
```

---

### Task 2: Regra de dependência e pipeline de CI

**Files:**
- Modify: `pyproject.toml` (adicionar `[tool.importlinter]`)
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: pacote da Tarefa 1.
- Produces: jobs de CI com os nomes **`qualidade`** e **`seguranca`**, que a proteção de branch vai exigir.

- [ ] **Step 1: Contratos do import-linter em `pyproject.toml`**

```toml
[tool.importlinter]
root_package = "honeyant"

[[tool.importlinter.contracts]]
name = "core nao depende de nenhum modulo"
type = "forbidden"
source_modules = ["honeyant.core"]
forbidden_modules = ["honeyant.arapuca", "honeyant.intel", "honeyant.twin", "honeyant.sensor",
                     "honeyant.pathfinder", "honeyant.painel", "honeyant.apps"]

[[tool.importlinter.contracts]]
name = "modulos nao importam uns aos outros"
type = "independence"
modules = ["honeyant.arapuca", "honeyant.intel", "honeyant.twin", "honeyant.sensor",
           "honeyant.pathfinder", "honeyant.painel"]

[[tool.importlinter.contracts]]
name = "somente apps e o composition root"
type = "forbidden"
source_modules = ["honeyant.core", "honeyant.arapuca", "honeyant.intel", "honeyant.twin",
                  "honeyant.sensor", "honeyant.pathfinder", "honeyant.painel"]
forbidden_modules = ["honeyant.apps"]
```

- [ ] **Step 2: Provar que o contrato pega uma violação**

Criar temporariamente `src/honeyant/intel/violacao.py` com `import honeyant.arapuca` e rodar `uv run lint-imports`.
Expected: `Contracts: 2 kept, 1 broken.` citando "modulos nao importam uns aos outros". **Apagar o arquivo** e rodar de novo → `3 kept, 0 broken`.

- [ ] **Step 3: Escrever `.github/workflows/ci.yml`**

- Gatilhos: `pull_request` e `push` em `main`. `permissions: contents: read`.
- Job **`qualidade`** (ubuntu-latest): `actions/checkout`, `astral-sh/setup-uv`, `uv sync --locked`, depois `uv run ruff check .`, `uv run ruff format --check .`, `uv run lint-imports`, `uv run bandit -c pyproject.toml -r src`, `uv run pytest -m "not integration" -v`.
- Job **`seguranca`**: checkout com `fetch-depth: 0`; `gitleaks/gitleaks-action@v2` (com `GITHUB_TOKEN`); `uv export --format requirements-txt --no-hashes --no-dev -o req.txt` seguido de `uvx pip-audit -r req.txt`.
- Fixar as actions por tag de versão maior (`@v4`, `@v6` etc.), conferindo a versão atual de cada uma no Marketplace no momento de escrever.

- [ ] **Step 4: Verificar localmente o que der**

Run: `uv run lint-imports ; uv run bandit -c pyproject.toml -r src ; uv run pytest -m "not integration"`
Expected: `3 kept, 0 broken`; bandit `No issues identified.`; testes passam.

- [ ] **Step 5: Commit, push e PR (Lucas)**

```powershell
git add pyproject.toml uv.lock .github/workflows/ci.yml
git commit -m "ci: adiciona regra de dependencia e pipeline com lint, testes e seguranca"
git push -u origin feat/fundacao
```
Abrir o PR `feat/fundacao → main` no GitHub. Expected: jobs `qualidade` e `seguranca` verdes. Um integrante revisa e aprova; merge.

- [ ] **Step 6: Completar o ruleset da `main` (Lucas, no GitHub)**

O ruleset já existe, com 1 aprovação e bypass para o admin. Falta acrescentar: **status checks obrigatórios `qualidade` e `seguranca`** (eles só aparecem para seleção depois da primeira execução do CI neste PR) e o bloqueio de force push. Adicionar os 4 colegas como colaboradores com permissão de escrita.

O bypass do admin fica **só para emergência**. O edital pede PRs revisados, então todo merge feito por bypass precisa ser justificado na descrição do PR.

---

### Task 3: Contrato `EventoDeAtaque` no `core`

**Files:**
- Create: `src/honeyant/core/texto.py`, `src/honeyant/core/eventos.py`
- Test: `tests/unit/core/test_texto.py`, `tests/unit/core/test_eventos.py`

**Interfaces:**
- Produces:
  - `limpar(texto: str, limite: int) -> str`: remove caracteres de controle (categoria Unicode `Cc`) e trunca em `limite`.
  - `class Servico(StrEnum)`: `TELNET="telnet"`, `MQTT="mqtt"`, `HTTP="http"`, `UPNP="upnp"`, `LAN="lan"`.
  - `class EventoDeAtaque(BaseModel)` (frozen): `schema_version: Literal[1] = 1`, `id: UUID = uuid4`, `ts: datetime`, `servico: Servico`, `ip_origem: IPv4Address | IPv6Address`, `pais: str | None = None`, `asn: int | None = None`, `usuario: str | None = None`, `senha: str | None = None`, `comandos: list[str] = []`, `bytes_recebidos: int = 0` (≥ 0).
  - Constantes: `LIMITE_CREDENCIAL = 64`, `LIMITE_COMANDOS = 20`, `LIMITE_COMANDO = 256`.

- [ ] **Step 1: Testes**

```python
# tests/unit/core/test_texto.py
from honeyant.core.texto import limpar

def test_remove_controles_e_escape_ansi():
    assert limpar("ad\x00min\x1b[31m", 64) == "admin[31m"

def test_trunca_no_limite():
    assert limpar("a" * 100, 64) == "a" * 64

def test_preserva_unicode_imprimivel():
    assert limpar("senha<script>çã", 64) == "senha<script>çã"   # escapar é papel de quem exibe
```

```python
# tests/unit/core/test_eventos.py
from datetime import datetime, timezone
from ipaddress import IPv4Address
import pytest
from pydantic import ValidationError
from honeyant.core.eventos import EventoDeAtaque, Servico

AGORA = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

def evento(**extra):
    return EventoDeAtaque(ts=AGORA, servico=Servico.TELNET, ip_origem="203.0.113.7", **extra)

def test_trunca_credenciais_e_comandos():
    e = evento(usuario="u" * 100, senha="s" * 100, comandos=["c" * 300] * 30)
    assert len(e.usuario) == 64 and len(e.senha) == 64
    assert len(e.comandos) == 20 and all(len(c) == 256 for c in e.comandos)

def test_rejeita_ts_sem_fuso():
    with pytest.raises(ValidationError):
        EventoDeAtaque(ts=datetime(2026, 11, 5), servico=Servico.MQTT, ip_origem="203.0.113.7")

def test_ipv4_mapeado_em_ipv6_vira_ipv4():
    assert evento(ip_origem="::ffff:203.0.113.7").ip_origem == IPv4Address("203.0.113.7")

def test_pais_normalizado_ou_rejeitado():
    assert evento(pais="br").pais == "BR"
    with pytest.raises(ValidationError):
        evento(pais="Brasil")

def test_credenciais_ausentes_sao_permitidas():
    e = evento()
    assert e.usuario is None and e.senha is None and e.comandos == []

def test_evento_e_imutavel():
    with pytest.raises(ValidationError):
        evento().senha = "x"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core -v`
Expected: FAIL com `ModuleNotFoundError: honeyant.core.texto`.

- [ ] **Step 3: Implementar `limpar` e `EventoDeAtaque`**

`limpar` usa `unicodedata.category(c) != "Cc"`. No modelo: `model_config = ConfigDict(frozen=True)`; validadores `field_validator(mode="before")` para truncar `usuario`/`senha`/`comandos` com `limpar`; `ts` exige `tzinfo` e converte para UTC; `ip_origem` usa `ipv4_mapped` quando houver; `pais` aceita `[A-Za-z]{2}` e grava em maiúsculas.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core -v`
Expected: 9 passed

- [ ] **Step 5: Commit (Lucas)**

```powershell
git switch main ; git pull ; git switch -c feat/arapuca
git add src/honeyant/core/texto.py src/honeyant/core/eventos.py tests/unit/core
git commit -m "feat(core): adiciona contrato EventoDeAtaque com truncamento e normalizacao"
```

---

### Task 4: Repositório de eventos (porta, memória e SQLite)

**Files:**
- Create: `src/honeyant/arapuca/ports.py`, `src/honeyant/arapuca/adapters/memoria.py`, `src/honeyant/arapuca/adapters/sqlite.py`
- Test: `tests/unit/arapuca/test_repositorio.py` (parametrizado nos dois adaptadores)

**Interfaces:**
- Consumes: `EventoDeAtaque`, `Servico` (Tarefa 3).
- Produces, em `ports.py`:
  ```python
  RETENCAO = timedelta(days=7); TETO_EVENTOS = 200_000; TETO_BYTES = 200 * 1024 * 1024
  class RepositorioDeEventos(Protocol):
      def salvar(self, evento: EventoDeAtaque) -> None: ...
      def contar(self) -> int: ...
      def acumulado_por_servico(self) -> dict[Servico, int]: ...
      def aplicar_limites(self, agora: datetime) -> int: ...   # devolve quantos removeu
  ```
- `RepositorioEmMemoria(teto_eventos: int = TETO_EVENTOS)`, `RepositorioSqlite(caminho: Path, teto_eventos: int = TETO_EVENTOS, teto_bytes: int = TETO_BYTES)`.

- [ ] **Step 1: Criar `tests/conftest.py`** com as fixtures `agora` (`datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)`) e `fabrica_evento` (devolve uma função `(**extra) -> EventoDeAtaque` com padrões `ts=agora`, `servico=Servico.TELNET`, `ip_origem="203.0.113.7"`). Atualizar `tests/unit/core/test_eventos.py` para usar essas fixtures no lugar do helper local.

- [ ] **Step 2: Testes**

```python
# tests/unit/arapuca/test_repositorio.py
from datetime import timedelta
import pytest
from honeyant.arapuca.adapters.memoria import RepositorioEmMemoria
from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.core.eventos import Servico
# reutilizar AGORA e evento(**extra) da Tarefa 3 via tests/conftest.py (fixture `fabrica_evento`)

@pytest.fixture(params=["memoria", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memoria":
        return RepositorioEmMemoria(teto_eventos=5)
    return RepositorioSqlite(tmp_path / "isca.db", teto_eventos=5)

def test_salva_e_conta(repo, fabrica_evento):
    repo.salvar(fabrica_evento()); repo.salvar(fabrica_evento(servico=Servico.MQTT))
    assert repo.contar() == 2
    assert repo.acumulado_por_servico() == {Servico.TELNET: 1, Servico.MQTT: 1}

def test_retencao_remove_antigos_mas_nao_o_acumulado(repo, fabrica_evento, agora):
    repo.salvar(fabrica_evento(ts=agora - timedelta(days=8)))
    repo.salvar(fabrica_evento(ts=agora))
    assert repo.aplicar_limites(agora) == 1
    assert repo.contar() == 1
    assert repo.acumulado_por_servico()[Servico.TELNET] == 2

def test_teto_descarta_os_mais_antigos(repo, fabrica_evento, agora):
    for i in range(8):
        repo.salvar(fabrica_evento(ts=agora - timedelta(minutes=10 - i), usuario=f"u{i}"))
    repo.aplicar_limites(agora)
    assert repo.contar() == 5

def test_sqlite_persiste_apos_reabrir(tmp_path, fabrica_evento):
    caminho = tmp_path / "isca.db"
    RepositorioSqlite(caminho).salvar(fabrica_evento())
    reaberto = RepositorioSqlite(caminho)
    assert reaberto.contar() == 1
    assert reaberto.acumulado_por_servico()[Servico.TELNET] == 1

def test_sqlite_usa_wal(tmp_path):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    assert repo.modo_journal() == "wal"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/unit/arapuca/test_repositorio.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: Implementar**

SQLite: `PRAGMA journal_mode=WAL` na abertura; tabela `eventos(id TEXT PRIMARY KEY, ts TEXT, servico TEXT, dados TEXT)` com `dados` = `model_dump_json()` e índice em `ts`; tabela `acumulado(servico TEXT PRIMARY KEY, total INTEGER)` atualizada **na mesma transação** do insert (`INSERT ... ON CONFLICT DO UPDATE SET total = total + 1`). `aplicar_limites`: apaga `ts < agora - RETENCAO`; depois, se `contar() > teto_eventos` ou `page_count * page_size > teto_bytes`, apaga os mais antigos até respeitar os tetos (no teto de bytes, em lotes de 1000); `VACUUM` não é necessário. Toda SQL é parametrizada (bandit). `modo_journal()` devolve `PRAGMA journal_mode`.

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest tests/unit/arapuca/test_repositorio.py -v`
Expected: 8 passed (3 testes × 2 adaptadores + `test_sqlite_persiste_apos_reabrir` + `test_sqlite_usa_wal`).

- [ ] **Step 6: Commit (Lucas)**

```powershell
git add src/honeyant/arapuca/ports.py src/honeyant/arapuca/adapters tests/conftest.py tests/unit/core/test_eventos.py tests/unit/arapuca/test_repositorio.py
git commit -m "feat(arapuca): adiciona repositorio de eventos em memoria e SQLite com retencao e teto"
```

---

### Task 5: Leitor limitado e limitador de conexões

**Files:**
- Create: `src/honeyant/arapuca/leitor.py`, `src/honeyant/arapuca/limites.py`
- Test: `tests/unit/arapuca/test_leitor.py`, `tests/unit/arapuca/test_limites.py`

**Interfaces:**
- Produces:
  - `class LimiteExcedido(Exception)`.
  - `LeitorLimitado(leitor: asyncio.StreamReader, max_bytes: int = 8192, ocioso_s: float = 15.0)` com `async ler_linha(max_linha: int = 256) -> bytes | None` (sem `\r\n`; `None` no EOF), `async ler_exato(n: int) -> bytes`, propriedade `bytes_lidos: int`. Lança `LimiteExcedido` ao passar de `max_bytes` e `TimeoutError` após `ocioso_s` sem dados.
  - `Limitador(max_total: int = 200, max_por_ip: int = 4, taxa_por_minuto: int = 20, relogio: Callable[[], float] = time.monotonic)` com `entrar(ip: str) -> bool` e `sair(ip: str) -> None`.

- [ ] **Step 1: Testes**

```python
# tests/unit/arapuca/test_leitor.py
import asyncio, pytest
from honeyant.arapuca.leitor import LeitorLimitado, LimiteExcedido

def leitor_com(dados: bytes, eof: bool = True) -> asyncio.StreamReader:
    r = asyncio.StreamReader(); r.feed_data(dados)
    if eof: r.feed_eof()
    return r

async def test_le_linhas_sem_crlf():
    l = LeitorLimitado(leitor_com(b"root\r\nadmin\n"))
    assert await l.ler_linha() == b"root"
    assert await l.ler_linha() == b"admin"
    assert await l.ler_linha() is None

async def test_linha_longa_e_cortada():
    l = LeitorLimitado(leitor_com(b"x" * 500 + b"\n"))
    assert len(await l.ler_linha(max_linha=256)) == 256

async def test_estoura_limite_de_bytes():
    l = LeitorLimitado(leitor_com(b"a\n" * 100), max_bytes=50)
    with pytest.raises(LimiteExcedido):
        while await l.ler_linha() is not None: pass

async def test_ocioso_gera_timeout():
    l = LeitorLimitado(leitor_com(b"", eof=False), ocioso_s=0.05)
    with pytest.raises(TimeoutError):
        await l.ler_linha()
```

```python
# tests/unit/arapuca/test_limites.py
from honeyant.arapuca.limites import Limitador

class Relogio:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

def test_limite_por_ip_e_liberacao():
    lim = Limitador(max_por_ip=2)
    assert lim.entrar("1.1.1.1") and lim.entrar("1.1.1.1")
    assert not lim.entrar("1.1.1.1")
    lim.sair("1.1.1.1")
    assert lim.entrar("1.1.1.1")

def test_limite_total():
    lim = Limitador(max_total=2, max_por_ip=5)
    assert lim.entrar("1.1.1.1") and lim.entrar("2.2.2.2")
    assert not lim.entrar("3.3.3.3")

def test_taxa_por_minuto_reinicia_apos_60s():
    rel = Relogio(); lim = Limitador(max_por_ip=100, taxa_por_minuto=3, relogio=rel)
    for _ in range(3):
        assert lim.entrar("1.1.1.1"); lim.sair("1.1.1.1")
    assert not lim.entrar("1.1.1.1")
    rel.t = 61.0
    assert lim.entrar("1.1.1.1")
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/arapuca/test_leitor.py tests/unit/arapuca/test_limites.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar.** No leitor, usar `asyncio.wait_for(leitor.read(1), ocioso_s)` byte a byte, ou `readuntil` com o limite. Na taxa, usar uma janela deslizante (`deque` de instantes por IP) e descartar IPs sem conexões ativas e com a janela vazia, para que o dicionário não cresça sem limite.

- [ ] **Step 4: Rodar e ver passar** — mesmo comando → 7 passed.

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/arapuca/leitor.py src/honeyant/arapuca/limites.py tests/unit/arapuca/test_leitor.py tests/unit/arapuca/test_limites.py
git commit -m "feat(arapuca): adiciona leitor limitado e limitador de conexoes por IP"
```

---

### Task 6: Serviço falso Telnet

**Files:**
- Modify: `src/honeyant/arapuca/ports.py` (acrescentar `Captura` e `ServicoFalso`)
- Create: `src/honeyant/arapuca/telnet.py`
- Test: `tests/unit/arapuca/test_telnet.py`, `tests/security/test_telnet_hostil.py`

**Interfaces:**
- Consumes: `LeitorLimitado`, `LimiteExcedido` (Tarefa 5); `Servico` (Tarefa 3).
- Produces, em `ports.py`:
  ```python
  @dataclass
  class Captura:
      usuario: str | None = None; senha: str | None = None
      comandos: list[str] = field(default_factory=list); bytes_recebidos: int = 0
  Escrever = Callable[[bytes], Awaitable[None]]
  class ServicoFalso(Protocol):
      servico: Servico
      async def atender(self, leitor: LeitorLimitado, escrever: Escrever) -> Captura: ...
  ```
  Em `telnet.py`: `remover_iac(dados: bytes) -> bytes`; `class ServicoTelnet` (`servico = Servico.TELNET`). **`atender` nunca lança exceção:** em EOF, `LimiteExcedido` ou `TimeoutError`, devolve o que capturou até ali.

Roteiro fixo: envia `b"\r\nlogin: "`, lê o usuário, envia `b"Password: "`, lê a senha e **sempre aceita o login**. A partir daí envia o prompt `b"$ "` e lê até 20 comandos. Respostas fixas: `uname -a` → `Linux camera 3.10.14 #1 PREEMPT armv7l GNU/Linux`; `whoami` → `root`; qualquer outro → `-sh: command not found`; `exit`/`logout` encerra. Nada é executado e nada vindo do atacante é ecoado de volta.

- [ ] **Step 1: Testes**

```python
# tests/unit/arapuca/test_telnet.py
from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.telnet import ServicoTelnet, remover_iac
# Neste passo, mover leitor_com() da Tarefa 5 para tests/conftest.py como fixture
# `leitor_com` que devolve a função; atualizar test_leitor.py para usá-la.

def test_remover_iac():
    assert remover_iac(b"\xff\xfb\x01ro\xff\xffot\xff\xfa\x18\x00\xff\xf0") == b"ro\xffot"

async def test_captura_login_senha_e_comandos(leitor_com):
    enviado = bytearray()
    async def escrever(b): enviado.extend(b)
    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"root\r\nxc3511\r\nuname -a\r\ncat /etc/passwd\r\nexit\r\n")), escrever)
    assert (cap.usuario, cap.senha) == ("root", "xc3511")
    assert cap.comandos == ["uname -a", "cat /etc/passwd"]
    assert b"armv7l" in enviado and b"command not found" in enviado

async def test_para_em_20_comandos(leitor_com):
    async def escrever(b): pass
    cap = await ServicoTelnet().atender(LeitorLimitado(leitor_com(b"u\np\n" + b"ls\n" * 50)), escrever)
    assert len(cap.comandos) == 20
```

```python
# tests/security/test_telnet_hostil.py
import os
from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.telnet import ServicoTelnet

async def nada(b): pass

async def test_binario_e_utf8_invalido_nao_quebram(leitor_com):
    cap = await ServicoTelnet().atender(LeitorLimitado(leitor_com(b"\xff\xfd\x03\x80\xfe\xc3(\n" + os.urandom(64) + b"\n")), nada)
    assert cap.usuario is not None and "�" in cap.usuario

async def test_payload_gigante_encerra_sem_excecao(leitor_com):
    cap = await ServicoTelnet().atender(LeitorLimitado(leitor_com(b"A" * 100_000), max_bytes=8192), nada)
    assert cap.bytes_recebidos <= 8192

async def test_xss_e_injecao_sao_guardados_como_texto(leitor_com):
    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"<script>alert(1)</script>\n; rm -rf / #\n$(reboot)\n")), nada)
    assert cap.usuario == "<script>alert(1)</script>" and cap.comandos == ["$(reboot)"]
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/arapuca/test_telnet.py tests/security/test_telnet_hostil.py -v` → FAIL.

- [ ] **Step 3: Implementar.** Cada linha passa por `remover_iac` e depois por `.decode("utf-8", errors="replace")`. A truncagem fica com o `EventoDeAtaque`. `bytes_recebidos` vem de `leitor.bytes_lidos`.

- [ ] **Step 4: Rodar e ver passar** — 6 passed.

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/arapuca/ports.py src/honeyant/arapuca/telnet.py tests/conftest.py tests/unit/arapuca/test_telnet.py tests/security/test_telnet_hostil.py
git commit -m "feat(arapuca): adiciona servico Telnet falso de baixa interacao"
```

---

### Task 7: Serviço falso MQTT

**Files:**
- Create: `src/honeyant/arapuca/mqtt.py`
- Test: `tests/unit/arapuca/test_mqtt.py`, `tests/security/test_mqtt_hostil.py`

**Interfaces:**
- Consumes: `Captura`, `ServicoFalso`, `Escrever` (Tarefa 6); `LeitorLimitado` (Tarefa 5).
- Produces: `async ler_varint(leitor: LeitorLimitado) -> int` (no máximo 4 bytes, senão `LimiteExcedido`); `class ServicoMqtt` (`servico = Servico.MQTT`, `max_pacote: int = 4096`), cujo `atender` nunca lança exceção.

Comportamento:
1. **CONNECT** (`0x10`): suporta os níveis de protocolo 4 (3.1.1) e 5. No nível 5, pula o bloco de propriedades e, havendo will, as propriedades do will. Lê o client id, o will (se a flag estiver ligada), o usuário (flag `0x80`) e a senha (flag `0x40`). Responde CONNACK aceito: `b"\x20\x02\x00\x00"` no nível 4 e `b"\x20\x03\x00\x00\x00"` no nível 5.
2. Depois, lê até 20 pacotes:
   - PUBLISH (`0x3?`) → comando `"PUBLISH <tópico>"`;
   - SUBSCRIBE (`0x82`) → `"SUBSCRIBE <primeiro filtro>"`, respondendo SUBACK com QoS 0;
   - PINGREQ (`0xC0`) → PINGRESP `b"\xd0\x00"`;
   - DISCONNECT (`0xE0`) encerra; qualquer outro tipo também encerra.
3. Pacote com remaining length acima de `max_pacote` encerra a sessão **sem ler o corpo**.

- [ ] **Step 1: Testes**

```python
# tests/unit/arapuca/test_mqtt.py
import struct
from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.mqtt import ServicoMqtt

def s(txt: str) -> bytes:
    b = txt.encode(); return struct.pack("!H", len(b)) + b

def connect_311(usuario="camera", senha="123456") -> bytes:
    corpo = s("MQTT") + b"\x04" + b"\xc2" + b"\x00\x3c" + s("cli1") + s(usuario) + s(senha)
    return b"\x10" + bytes([len(corpo)]) + corpo

def publish(topico: str, payload: bytes = b"on") -> bytes:
    corpo = s(topico) + payload
    return b"\x30" + bytes([len(corpo)]) + corpo

async def test_captura_credenciais_e_publish(leitor_com):
    enviado = bytearray()
    async def escrever(b): enviado.extend(b)
    dados = connect_311() + publish("casa/fechadura/cmd") + b"\xe0\x00"
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(dados)), escrever)
    assert (cap.usuario, cap.senha) == ("camera", "123456")
    assert cap.comandos == ["PUBLISH casa/fechadura/cmd"]
    assert enviado.startswith(b"\x20\x02\x00\x00")

async def test_connect_v5_com_propriedades(leitor_com):
    corpo = s("MQTT") + b"\x05" + b"\xc2" + b"\x00\x3c" + b"\x05\x11\x00\x00\x00\x0a" + s("c") + s("adm") + s("pw")
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"\x10" + bytes([len(corpo)]) + corpo)), lambda b: _nada())
    assert (cap.usuario, cap.senha) == ("adm", "pw")

async def _nada(): pass
```

```python
# tests/security/test_mqtt_hostil.py
from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.mqtt import ServicoMqtt

async def nada(b): pass

async def test_varint_com_mais_de_4_bytes_encerra(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"\x10\xff\xff\xff\xff\x7f" + b"x" * 100)), nada)
    assert cap.usuario is None and cap.bytes_recebidos <= 6

async def test_remaining_length_acima_do_limite_nao_le_o_corpo(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"\x10\xff\xff\x03" + b"x" * 70_000)), nada)
    assert cap.bytes_recebidos <= 4

async def test_connect_truncado_nao_lanca(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"\x10\x20\x00\x04MQ")), nada)
    assert cap.usuario is None

async def test_primeiro_pacote_nao_connect_encerra(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"GET / HTTP/1.1\r\n\r\n")), nada)
    assert cap.comandos == []
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/arapuca/test_mqtt.py tests/security/test_mqtt_hostil.py -v` → FAIL.

- [ ] **Step 3: Implementar.** Ler o corpo inteiro com `ler_exato(remaining)` e então interpretar em memória sobre `memoryview`. Um campo truncado lança `ValueError`, e o EOF no meio do corpo lança `asyncio.IncompleteReadError`. `atender` captura os dois, além de `LimiteExcedido` e `TimeoutError`, e trata como fim da sessão. Strings são decodificadas com `errors="replace"`.

- [ ] **Step 4: Rodar e ver passar** — 6 passed.

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/arapuca/mqtt.py tests/unit/arapuca/test_mqtt.py tests/security/test_mqtt_hostil.py
git commit -m "feat(arapuca): adiciona servico MQTT falso que registra CONNECT, PUBLISH e SUBSCRIBE"
```

---

### Task 8: Geolocalização offline e servidor da isca

**Files:**
- Modify: `src/honeyant/arapuca/ports.py` (acrescentar `ResolvedorGeo`)
- Create: `src/honeyant/arapuca/adapters/geo.py`, `src/honeyant/arapuca/servidor.py`
- Test: `tests/unit/arapuca/test_geo.py`, `tests/integration/test_servidor_isca.py`

**Interfaces:**
- Consumes: Tarefas 3 a 7.
- Produces:
  - `class ResolvedorGeo(Protocol): def resolver(self, ip: str) -> tuple[str | None, int | None]: ...`
  - `GeoNulo()` (sempre `(None, None)`); `GeoDbIp(caminho_pais: Path, caminho_asn: Path)`, que lê `registro["country"]["iso_code"]` e `registro["autonomous_system_number"]` via `maxminddb` e devolve `None` em qualquer erro.
  - `ServidorDaIsca(servicos: dict[int, ServicoFalso], repositorio: RepositorioDeEventos, geo: ResolvedorGeo, limitador: Limitador, sessao_s: float = 60.0, ocioso_s: float = 15.0, max_bytes: int = 8192, host: str = "0.0.0.0")` com `async iniciar() -> dict[int, int]` (porta pedida → porta real; porta 0 = efêmera, usada nos testes), `async parar()` e `async ciclo_de_limites(intervalo_s: float = 60.0)`.

Por sessão: `limitador.entrar(ip)`; se recusado, fecha na hora. Senão, roda `servico.atender` dentro de `asyncio.timeout(sessao_s)` e grava o evento **inclusive quando não houve credencial** (uma varredura também é evidência). A gravação no SQLite vai por `asyncio.to_thread(repositorio.salvar, …)`. No `finally`, `limitador.sair(ip)` e fechamento do escritor. Os logs vão em JSON para stdout com `servico`, `pais` e `bytes`, **sem IP**.

- [ ] **Step 1: Testes**

```python
# tests/unit/arapuca/test_geo.py
from honeyant.arapuca.adapters.geo import GeoDbIp, GeoNulo

def test_geo_nulo():
    assert GeoNulo().resolver("203.0.113.7") == (None, None)

def test_geo_dbip_le_registros(monkeypatch, tmp_path):
    class Leitor:
        def __init__(self, dados): self.dados = dados
        def get(self, ip): return self.dados
    leitores = iter([Leitor({"country": {"iso_code": "BR"}}), Leitor({"autonomous_system_number": 28573})])
    monkeypatch.setattr("maxminddb.open_database", lambda caminho: next(leitores))
    assert GeoDbIp(tmp_path / "p.mmdb", tmp_path / "a.mmdb").resolver("203.0.113.7") == ("BR", 28573)

def test_geo_dbip_ip_invalido_devolve_none(monkeypatch, tmp_path):
    class Leitor:
        def get(self, ip): raise ValueError("ip invalido")
    monkeypatch.setattr("maxminddb.open_database", lambda caminho: Leitor())
    assert GeoDbIp(tmp_path / "p", tmp_path / "a").resolver("lixo") == (None, None)
```

```python
# tests/integration/test_servidor_isca.py
import asyncio, pytest
from honeyant.arapuca.adapters.geo import GeoNulo
from honeyant.arapuca.adapters.memoria import RepositorioEmMemoria
from honeyant.arapuca.limites import Limitador
from honeyant.arapuca.servidor import ServidorDaIsca
from honeyant.arapuca.telnet import ServicoTelnet
from honeyant.core.eventos import Servico

pytestmark = pytest.mark.integration

@pytest.fixture
async def isca():
    repo = RepositorioEmMemoria()
    srv = ServidorDaIsca({0: ServicoTelnet()}, repo, GeoNulo(), Limitador(max_por_ip=1), ocioso_s=0.2)
    portas = await srv.iniciar()
    yield srv, repo, portas[0]
    await srv.parar()

async def test_sessao_telnet_vira_evento(isca):
    _, repo, porta = isca
    r, w = await asyncio.open_connection("127.0.0.1", porta)
    w.write(b"root\r\nvizxv\r\nexit\r\n"); await w.drain()
    await r.read()  # servidor fecha
    await asyncio.sleep(0.1)
    assert repo.contar() == 1 and repo.acumulado_por_servico()[Servico.TELNET] == 1

async def test_cliente_mudo_e_encerrado_e_libera_vaga(isca):
    _, repo, porta = isca
    r, w = await asyncio.open_connection("127.0.0.1", porta)
    assert await asyncio.wait_for(r.read(), timeout=2) is not None   # fechado pelo ocioso
    await asyncio.sleep(0.1)
    r2, w2 = await asyncio.open_connection("127.0.0.1", porta)        # vaga do IP foi liberada
    w2.write(b"a\nb\nexit\n"); await w2.drain(); await r2.read()
    await asyncio.sleep(0.1)
    assert repo.contar() == 2      # a sessão muda também gera evento (varredura)
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/arapuca/test_geo.py tests/integration/test_servidor_isca.py -v` → FAIL.

- [ ] **Step 3: Implementar** `GeoNulo`, `GeoDbIp` e `ServidorDaIsca` conforme as Interfaces.

- [ ] **Step 4: Rodar e ver passar** — 5 passed. Depois rodar a suíte inteira: `uv run pytest -v` → tudo verde.

- [ ] **Step 5: Commit (Lucas)**

```powershell
git add src/honeyant/arapuca/ports.py src/honeyant/arapuca/adapters/geo.py src/honeyant/arapuca/servidor.py tests/unit/arapuca/test_geo.py tests/integration/test_servidor_isca.py
git commit -m "feat(arapuca): adiciona servidor asyncio da isca e geolocalizacao offline"
```

---

### Task 9: Composition root, imagem e compose da nuvem

**Files:**
- Create: `src/honeyant/apps/isca.py`, `infra/docker/Dockerfile.isca`, `infra/compose.cloud.yml`, `infra/scripts/baixar-dbip.sh`, `.dockerignore`
- Modify: `pyproject.toml` (`[project.scripts] honeyant-isca = "honeyant.apps.isca:main"`)
- Test: `tests/unit/apps/test_isca_config.py`

**Interfaces:**
- Consumes: `ServidorDaIsca`, `RepositorioSqlite`, `GeoDbIp`/`GeoNulo`, `Limitador`, `ServicoTelnet`, `ServicoMqtt`.
- Produces:
  - `ConfigIsca.do_ambiente(env: Mapping[str, str]) -> ConfigIsca`, com as variáveis `HONEYANT_DB` (padrão `/dados/isca.db`), `HONEYANT_GEO_DIR` (padrão `/geo`; se os arquivos não existirem, usa `GeoNulo` e registra um aviso), `HONEYANT_PORTA_TELNET` (padrão `2323`) e `HONEYANT_PORTA_MQTT` (padrão `18830`).
  - CLI `honeyant-isca servir` (padrão) e `honeyant-isca estatisticas`, que imprime em JSON o total atual e o acumulado por serviço, sem IPs.

- [ ] **Step 1: Teste**

```python
# tests/unit/apps/test_isca_config.py
from pathlib import Path
from honeyant.apps.isca import ConfigIsca

def test_padroes():
    c = ConfigIsca.do_ambiente({})
    assert (c.db, c.porta_telnet, c.porta_mqtt) == (Path("/dados/isca.db"), 2323, 18830)

def test_sobrescreve_por_ambiente():
    c = ConfigIsca.do_ambiente({"HONEYANT_DB": "x.db", "HONEYANT_PORTA_MQTT": "1999"})
    assert c.db == Path("x.db") and c.porta_mqtt == 1999
```

- [ ] **Step 2: Rodar e ver falhar; implementar `apps/isca.py`; rodar e ver passar** — `uv run pytest tests/unit/apps -v` → 2 passed. `uv run lint-imports` → `3 kept`, já que `apps` pode importar tudo.

- [ ] **Step 3: Script e imagem**

- `infra/scripts/baixar-dbip.sh`: baixa `https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz` e `dbip-asn-lite-…` para `/geo`, descompacta e, se o mês atual ainda não estiver publicado, tenta o mês anterior.
- `Dockerfile.isca`:
  - **estágio `geo`**: `debian:stable-slim` com `curl`, rodando o script;
  - **estágio `app`**: `python:3.12-slim`, instala o uv, roda `uv sync --locked --no-dev`, copia `/geo`, usa `USER 10001`, `EXPOSE 2323 18830` e `CMD ["honeyant-isca", "servir"]`.
- `compose.cloud.yml`, serviço `isca`:
  - `ports: ["23:2323", "1883:18830"]`
  - volume `dados:/dados`
  - `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`
  - `mem_limit: 256m`, `pids_limit: 128`, `restart: unless-stopped`
  - logging `json-file` com `max-size: 10m` e `max-file: "3"`
  - um serviço `init-dados` que roda uma vez para fazer `chown 10001` no volume

- [ ] **Step 4: Verificar localmente**

Run: `docker compose -f infra/compose.cloud.yml up -d --build`. Em seguida:
`uv run python -c "import socket;s=socket.create_connection(('127.0.0.1',23));s.sendall(b'root\r\n1234\r\nexit\r\n');print(s.recv(200))"`
e depois `docker compose -f infra/compose.cloud.yml exec isca honeyant-isca estatisticas`.
Expected: `{"total": 1, "acumulado": {"telnet": 1}}`. Por fim, `docker compose -f infra/compose.cloud.yml down`.

- [ ] **Step 5: Commit, push e PR (Lucas)**

```powershell
git add src/honeyant/apps/isca.py pyproject.toml uv.lock infra/docker/Dockerfile.isca infra/compose.cloud.yml infra/scripts/baixar-dbip.sh .dockerignore tests/unit/apps
git commit -m "feat(apps): adiciona composition root, imagem e compose da isca"
git push -u origin feat/arapuca
```
Abrir o PR `feat/arapuca → main` com **revisão do Rafael**. Para agilizar, a Tarefa 10 pode seguir em paralelo a partir desta branch.

---

### Task 10: Deploy na EC2 e ADR da isca

**Files:**
- Create: `infra/aws/DEPLOY.md`, `docs/adr/0004-isca-baixa-interacao.md`

**Interfaces:**
- Consumes: `infra/compose.cloud.yml` (Tarefa 9).
- Produces: isca acessível em `<IP-da-EC2>:23` e `:1883`, sem saída de rede.

- [ ] **Step 1: Escrever `infra/aws/DEPLOY.md`** com os passos abaixo. Os passos marcados como ✅ já foram feitos e entram no documento para que o deploy possa ser reproduzido:
  1. **Billing → Budgets:** criar um orçamento de custo mensal de **US$ 10**, com alertas por e-mail em 50% e 100%. Em Billing → Credits, verificar se a conta nova tem créditos promocionais.
  2. **Política de uso:** ler a Acceptable Use Policy da AWS e registrar o resultado no ADR (passo 2 desta tarefa) **antes** de subir a isca.
  3. ✅ **EC2:** t3.micro em us-east-1, 12 GB de disco, 2 GB de swap, Docker e Compose instalados.
  4. **Security Group:** conferir que a entrada é TCP 23 e TCP 1883 de `0.0.0.0/0` e `::/0`, mais TCP 22 apenas de "Meu IP"; ✅ saída sem nenhuma regra.
  5. **Janela de deploy** (✅ procedimento já documentado): abrir a saída TCP 80/443, rodar `git clone` do repositório público (ou `git pull`), depois `docker compose -f infra/compose.cloud.yml up -d --build`. **Fechar a saída** ao terminar.
     - O build baixa a base DB-IP e as dependências; com 1 GB de RAM, o swap evita erro de memória.
     - Antes do build, confirmar espaço livre com `df -h /`; ao final, rodar `docker image prune -f` para não lotar os 12 GB.
  6. **Conferir que a saída está bloqueada:** na instância, `curl -m 5 https://example.com` precisa falhar com timeout.
  7. **Conferir que a isca funciona:** no PC, `Test-NetConnection <IP> -Port 23` deve mostrar `TcpTestSucceeded : True`; depois de alguns minutos, `docker compose ... exec isca honeyant-isca estatisticas` deve mostrar `total` > 0.
  8. **No dia seguinte**, em Billing → Cost Explorer, confirmar que o gasto diário está dentro do previsto (R$ 20–50 até a apresentação), incluindo o IPv4 público, e anotar o valor.
  9. **Depois da ExpoTech (28/11):** desligar ou encerrar a instância e liberar o IP.
  - O documento **não** traz IP, ID de conta nem nome do par de chaves.

- [ ] **Step 2: Escrever `docs/adr/0004-isca-baixa-interacao.md`.** Seguir o formato Contexto / Decisão / Alternativas (Cowrie de alta interação, descartado pelo risco operacional) / Consequências / "Política de uso da AWS: verificada em <data>, link, conclusão" (preenchido pelo Lucas no passo 2 do deploy).

- [ ] **Step 3: Executar o deploy** seguindo o `DEPLOY.md`. Expected: o passo 6 falha (saída bloqueada) e o passo 7 mostra eventos chegando.

- [ ] **Step 4: Commit (Lucas)** — antes, Claude pergunta se o `DEPLOY.md` e o ADR podem ir ao público.

```powershell
git add infra/aws/DEPLOY.md docs/adr/0004-isca-baixa-interacao.md
git commit -m "docs: adiciona procedimento de deploy na EC2 e ADR da isca de baixa interacao"
git push
```

---

### Task 11: Teste de captura no notebook da apresentação (prova de viabilidade)

Esta tarefa responde a uma pergunta: **o tcpdump num container consegue gravar o tráfego MQTT da rede Docker para ser aberto no Wireshark do Windows?** Os arquivos ficam em `infra/teste-captura/` e servem de base para o `compose.local.yml` do Plano 2.

**Files:**
- Create: `infra/teste-captura/compose.yml`, `infra/teste-captura/mosquitto.conf`, `infra/teste-captura/LEIAME.md`

- [x] **Step 1: Instalar o Wireshark** no notebook da apresentação. ✅ Feito em 05/11.

- [x] **Step 2: Escrever os arquivos** ✅ Feito em 06/11. A tag `eclipse-mosquitto:2` publicada em 05/11 está quebrada (entrypoint vazio, binário sem OpenSSL); usamos `eclipse-mosquitto:2.0.20` fixada por digest.
  - `mosquitto.conf`: `listener 1883` e `allow_anonymous true`.
  - `compose.yml`:
    - `mosquitto`: `eclipse-mosquitto:2.0.20` (não a `:2`), com o conf montado;
    - `captura`: `nicolaka/netshoot`, com `network_mode: "service:mosquitto"`, `cap_add: [NET_RAW, NET_ADMIN]`, `command: tcpdump -i any -U -w /capturas/teste.pcap port 1883` e o volume `./capturas:/capturas`;
    - `cliente`: `eclipse-mosquitto:2.0.20`, com `command: mosquitto_pub -h mosquitto -u camera -P 123456 -t casa/teste -m oi` e `depends_on: [captura]`.
  - Depois do primeiro pull, fixar as imagens por digest (`docker image inspect --format "{{index .RepoDigests 0}}" <imagem>`).

- [x] **Step 3: Rodar** ✅ 06/11.

Run: `docker compose -f infra/teste-captura/compose.yml up` (deixar uns 5 s) e depois `docker compose -f infra/teste-captura/compose.yml down`.
Expected: o arquivo `infra/teste-captura/capturas/teste.pcap` existe e tem mais de 0 bytes.

- [x] **Step 4: Abrir no Wireshark** ✅ 06/11 (verificado com o TShark 4.6.9 do Windows).

Abrir o `teste.pcap` e aplicar o filtro `mqtt.conflags`. Expected: um pacote **Connect Command** com `User Name: camera` e `Password: 123456` legíveis.

- [x] **Step 5: Testar o modo ao vivo (Git Bash, não PowerShell)** ✅ 06/11 (pipe para o TShark).

Com o compose de pé (`up -d`):
```bash
docker compose -f infra/teste-captura/compose.yml exec -T captura tcpdump -i any -U -w - port 1883 | "/c/Program Files/Wireshark/Wireshark.exe" -k -i -
```
Em outro terminal: `docker compose -f infra/teste-captura/compose.yml run --rm cliente`. Expected: o Connect aparece ao vivo no Wireshark.

- [x] **Step 6: Registrar o resultado** ✅ 06/11 no `LEIAME.md` (funcionou ou não, versão do Docker Desktop, observações). Se o modo ao vivo falhar, o plano B é gravar o `.pcap` e abrir depois.

- [x] **Step 7: Commit (Lucas)** ✅ 06/11 — **o `.pcap` não entra** (só tem credencial de teste, mas não é a captura oficial).

```powershell
git add infra/teste-captura/compose.yml infra/teste-captura/mosquitto.conf infra/teste-captura/LEIAME.md
git commit -m "chore: adiciona teste de viabilidade da captura MQTT em container"
```

---

## Fora deste plano (próximos planos)

- **Plano 2:** contratos restantes do `core` (`ResumoDeAmeaca`, `PerfilDaCasa`, `EvidenciaDeRede`, `Rota`, `Snapshot`) com fixtures e exportação de JSON Schema no CI; esqueleto ponta a ponta em `apps/local`; teste do `mode=ro` na EC2.
- **Planos 3 a 7:** intel + sensor, twin, pathfinder, painel + formigueiro e a integração final (E2E, `.pcap` oficiais, ADRs restantes e diagramas).
