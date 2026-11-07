# Plano 3 — Painel e Formigueiro em grade (entregas 1 a 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o painel contar a história da demonstração (ataques reais → formigas → túnel até a fechadura → mitigação → túnel desmorona) numa rede de túneis em grade ortogonal em SVG (spec, seção 4; a cena 2.5D da primeira versão foi substituída em 07/11), com o ponto de encaixe do login entregue antes para o Gustavo.

**Architecture:** O `painel` continua importando só o `core` e recebe tudo por portas (`FonteDoFormigueiro`, `FonteDoResumo`). `apps/local.py` implementa as portas com fixtures, pathfinder e o resumo real exportado da isca. O front é JS puro em módulos ES: funções puras testadas com `node --test` (`estado.js`, `geometria.js`, `comparativo.js`, `risco.js`), mais a cena (`cena.js`) e a ligação (`app.js`).

**Tech Stack:** Python 3.12, FastAPI/Starlette (já no extra `painel`), pydantic v2, SQLite `mode=ro`, SVG + CSS + JavaScript puro (módulos ES), Node 20 (`node --test`) só para testes.

**Spec:** `docs/superpowers/specs/2026-11-06-painel-formigueiro-design.md` (com `AJUSTES-SPEC-PAINEL.md` já incorporado). O spec-mãe `2026-11-05-arapuca-honeyant-design.md` vale onde este não for mais específico.

## Global Constraints

- Tudo dos planos 1 e 2: Python 3.12, `uv.lock` commitado, nomes em português sem acento, nunca `git add .`, **nenhum `Co-Authored-By` nem atribuição ao Claude** em commits e PRs.
- `painel` importa só `core`; só `apps/` monta módulos (import-linter).
- **Sem bibliotecas novas** no Python nem no front (Three.js e D3 só com ADR). Sem CDN: ícones, CSS e JS servidos pelo painel.
- CSP atual sem mudanças: `default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`. JS só como `<script type="module" src>`, sem script, estilo ou `on*` inline.
- Proibido em todo `.js` estático: `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `new Function`, `srcdoc`.
- Stream: `perfil` ∈ {inseguro, seguro}; `modo` ∈ {prever, replay}; `velocidade` ∈ [0,25; 4]; `semente` ∈ [0; 2³¹−1]; nenhum parâmetro do ACO vem do cliente; espera `max(0,15, 0,6/velocidade)` s; **o mais novo vence** por IP de cliente.
- Hosts permitidos no modo local: `("127.0.0.1", "localhost")`; testes usam `base_url="http://127.0.0.1"`.
- Rota oficial = **Dijkstra**; a cena mostra a exploração do ACO.
- Geometria fixa: `viewBox="0 0 1000 640"`; `GRADE = 10`; entrada = círculo `RAIO_ENTRADA = 22`; `FOLGA = 12`; túnel normal de 4 a 18 px, rota 22 px, fundo 3 px; formigas = quadrados vermelhos de 7 px (ataque: 9 px com contorno claro); até 20 formigas; desmoronamento ~1,2 s; formiga de ataque a cada 2 s.
- Faixas de risco: < 0,3 baixo; < 0,6 médio; < 0,85 alto; senão crítico.
- Textos exatos: botão "Aplicar mitigação (perfil seguro)" / "Desfazer mitigação"; nota "Simulação do perfil mitigado. A mitigação real e as capturas estão em `docs/capturas/`."; origem do resumo "Ataques reais, congelados em <data>" / "Dados de exemplo"; selos "Vulnerável" / "Protegida"; sem rota: "nenhuma rota até a fechadura"; 401/403: "Sessão expirada. Entre de novo."
- **Antes de escrever CSS ou SVG da cena** (Tarefas 5, 7 e 9), carregue a skill `frontend-design:frontend-design` (direção visual) e, ao terminar, a `anthropic-skills:impeccable` (crítica e polimento), dentro da paleta e dos limites da seção 4.6 do spec.
- **Branches e PRs:** Tarefa 1 em `feat/painel-encaixe` (PR pequeno, revisor **Gustavo**); Tarefas 2–5 em `feat/painel-cena` (entrega 1); 6–7 em `feat/painel-mitigacao` (entrega 2); 8–9 em `feat/painel-isca` (entrega 3, revisor do `intel`: **Rafael**). Revisores do painel: **Kawe**. Cada branch sai da `main` depois do merge da anterior.
- **Caminho crítico:** antes da Tarefa 8, perguntar ao Lucas se a prova real (twin + `.pcap`) está encaminhada; se não, parar e avisar.

## Review Focus

1. **Duplo clique em "Prever invasão" ou duas abas abertas** → só o stream mais novo continua e a cena nunca mistura snapshots de duas execuções. Testes nas Tarefas 2 (servidor) e 4 (`aceitarSnapshot`).
2. **Isca sem nenhum ataque na janela de 24 h** → resumo válido com `total_eventos = 0`, cartão "nenhum ataque nas últimas 24 h", rota da demo inalterada (conferido em 06/11: vazio, só Telnet ou só MQTT mantêm as duas rotas). Teste na Tarefa 8.
3. **Senha hostil vinda da isca** (`<img src=x onerror=alert(1)>`, caracteres de controle, mais de 64 caracteres) → aparece limpa e como texto no cartão. Teste na Tarefa 9.
4. **`prefers-reduced-motion`** → nenhuma formiga anda, o desmoronamento vai direto ao estado final e a tela mostra o último snapshot. Teste na Tarefa 7 (`planoDeAnimacao`).
5. **Projetor em 1024×768 ou zoom de 125%** → sem rolagem horizontal; o painel lateral desce para baixo da cena. Verificação visual na Tarefa 5, com a regra CSS `@media (max-width: 1180px)`.

---

## Estrutura de arquivos

```
src/honeyant/painel/app.py            # fábrica: routers api/pagina, proteção, TrustedHost, stream
src/honeyant/painel/ports.py          # FonteDoFormigueiro, FonteDoResumo
src/honeyant/painel/modelos.py        # AnaliseDeRota, ResumoComOrigem
src/honeyant/painel/streams.py        # RegistroDeStreams ("o mais novo vence")
src/honeyant/painel/static/index.html
src/honeyant/painel/static/painel.css
src/honeyant/painel/static/icones.svg
src/honeyant/painel/static/layout.json
src/honeyant/painel/static/js/package.json   # {"type": "module"} (para o node --test)
src/honeyant/painel/static/js/{estado,geometria,comparativo,risco,cena,app}.js
src/honeyant/pathfinder/prever.py     # + analisar_rota
src/honeyant/intel/resumo.py          # agregar(): eventos → ResumoDeAmeaca
src/honeyant/intel/adapters/sqlite_leitura.py  # + eventos_desde
src/honeyant/apps/local.py            # adaptadores das portas
src/honeyant/apps/gravar_replay.py    # honeyant-gravar-replay
src/honeyant/apps/exportar_resumo.py  # honeyant-exportar-resumo
docs/demo/replay-{inseguro,seguro}.jsonl, docs/demo/resumo-real-AAAA-MM-DD.json
tests/js/*.test.mjs
.github/workflows/ci.yml              # + setup-node e node --test
```

Os arquivos antigos `static/formigueiro.js` e `static/formigueiro.css` são removidos na Tarefa 5.

---

## Entrega 1 — Página e formigueiro em grade

### Task 1: Ponto de encaixe do login e TrustedHost (PR para o Gustavo)

**Files:**
- Modify: `src/honeyant/painel/app.py`, `src/honeyant/apps/local.py` (passa `hosts_permitidos`)
- Test: `tests/unit/painel/test_encaixe.py`; ajustar `tests/unit/painel/test_app.py`, `test_static.py` e `tests/e2e/test_esqueleto.py` para `base_url="http://127.0.0.1"`

**Interfaces:**
- Produces:
  - `painel/app.py`: `@dataclass(frozen=True) class Encaixe: protecao_api: Sequence[params.Depends] = (); protecao_pagina: Sequence[params.Depends] = (); routers: Sequence[APIRouter] = ()`.
  - `criar_app(perfil, fonte, intervalo_base=0.6, intervalo_minimo=0.15, dormir=asyncio.sleep, *, encaixe: Encaixe = Encaixe(), hosts_permitidos: Sequence[str] = ("127.0.0.1", "localhost")) -> FastAPI`. As rotas atuais passam para `api = APIRouter(prefix="/api/v1", dependencies=list(encaixe.protecao_api))` e `pagina = APIRouter(dependencies=list(encaixe.protecao_pagina))` (`/`). Duas proteções porque a API responde 401 e a página redireciona (303) para `/login`. `encaixe.routers` entram **sem** proteção, antes dos outros. `/static` continua montado e público: `StaticFiles` não aceita dependências, e os estáticos são o mesmo código que está no GitHub, sem dado nenhum. Registrar isso numa docstring. `TrustedHostMiddleware(allowed_hosts=list(hosts_permitidos))`.
  - `apps/local.py`: `montar(config, ..., encaixe: Encaixe = Encaixe())` repassa para `criar_app`. O PR do Gustavo cria `apps/painel_login.py` com `encaixe_do_ambiente() -> Encaixe` (lê `HONEYANT_PAINEL_LOGIN` e falha na partida se a configuração estiver inválida) e muda uma linha em `main()`: `montar(config, encaixe=encaixe_do_ambiente())`.

- [ ] **Step 1: Testes que falham** em `test_encaixe.py`:

```python
def recusa_api(): raise HTTPException(401)
def recusa_pagina(): raise HTTPException(303, headers={"Location": "/login"})
ENCAIXE = Encaixe(protecao_api=[Depends(recusa_api)], protecao_pagina=[Depends(recusa_pagina)])

@pytest.mark.parametrize("rota", ["/api/v1/perfil", "/api/v1/formigueiro/stream"])
def test_protecao_da_api_responde_401(rota):
    c = TestClient(criar_app(perfil, fonte, encaixe=ENCAIXE), base_url="http://127.0.0.1")
    assert c.get(rota).status_code == 401

def test_protecao_da_pagina_redireciona_para_o_login():
    c = TestClient(criar_app(perfil, fonte, encaixe=ENCAIXE), base_url="http://127.0.0.1",
                   follow_redirects=False)
    r = c.get("/")
    assert r.status_code == 303 and r.headers["location"] == "/login"

def test_routers_do_encaixe_ficam_fora_da_protecao():
    extra = APIRouter(); extra.get("/login")(lambda: {"ok": True})
    enc = Encaixe(ENCAIXE.protecao_api, ENCAIXE.protecao_pagina, routers=[extra])
    c = TestClient(criar_app(perfil, fonte, encaixe=enc), base_url="http://127.0.0.1")
    assert c.get("/login").status_code == 200

def test_host_desconhecido_recebe_400():
    c = TestClient(criar_app(perfil, fonte), base_url="http://127.0.0.1")
    assert c.get("/api/v1/perfil", headers={"Host": "evil.com"}).status_code == 400

def test_localhost_e_aceito():
    assert TestClient(criar_app(perfil, fonte), base_url="http://localhost").get("/").status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/painel/test_encaixe.py -q` → FAIL (`Encaixe` não existe).
- [ ] **Step 3: Implementar** a fábrica com routers, proteção, extras e TrustedHost.
- [ ] **Step 4: Rodar e ver passar**: `uv run pytest -m "not integration" -q` → tudo verde (os testes antigos com `base_url` ajustado).
- [ ] **Step 5: Commit e PR**

```powershell
git add src/honeyant/painel/app.py src/honeyant/apps/local.py tests/unit/painel/test_encaixe.py tests/unit/painel/test_app.py tests/unit/painel/test_static.py tests/e2e/test_esqueleto.py
git commit -m "feat(painel): adiciona ponto de encaixe do login e protecao contra DNS rebinding"
```
Push de `feat/painel-encaixe` e PR (revisor Gustavo). A descrição do PR mostra o uso: `Encaixe(protecao_api=[Depends(exigir_sessao_api)], protecao_pagina=[Depends(exigir_sessao_pagina)], routers=[router_login])`, e diz que `login.css`/`login.js` são servidos pelo router dele (`/login/login.css`) ou ficam em `static/`, que é público.

---

### Task 2: Portas, modelos e API novas do painel

**Files:**
- Create: `src/honeyant/painel/modelos.py`, `src/honeyant/painel/streams.py`
- Modify: `src/honeyant/painel/ports.py`, `src/honeyant/painel/app.py`
- Test: `tests/unit/painel/test_api.py` (substitui `test_app.py`; os casos que continuam valendo migram para cá); ajustar `test_encaixe.py` e `test_static.py` para a nova assinatura de `criar_app` e trocar `/api/v1/perfil` por `/api/v1/casa`

**Interfaces:**
- Consumes: `criar_app` da Tarefa 1.
- Produces:
  - `modelos.py`: `AnaliseDeRota(rota: Rota | None, riscos: dict[ChaveDeAresta, float], riscos_por_no: dict[IdDeNo, float], bloqueadas: list[ChaveDeAresta])`; `ResumoComOrigem(origem: Literal["real", "exemplo"], resumo: ResumoDeAmeaca)`. Ambos `frozen`, `extra="forbid"`; riscos em [0, 1].
  - `ports.py`: `FonteDoFormigueiro.snapshots(perfil: TipoDePerfil, semente: int) -> Sequence[Snapshot]`, `.replay(perfil) -> Sequence[Snapshot] | None`, `.analise(perfil) -> AnaliseDeRota`; `FonteDoResumo.resumo() -> ResumoComOrigem`.
  - `streams.py`: `RegistroDeStreams` com `abrir(cliente: str) -> asyncio.Event` (encerra o evento do stream anterior do mesmo cliente e devolve um novo) e `fechar(cliente, evento)`.
  - `criar_app(casas: Mapping[TipoDePerfil, PerfilDaCasa], fonte: FonteDoFormigueiro, fonte_resumo: FonteDoResumo, intervalo_base=..., intervalo_minimo=..., dormir=..., *, encaixe=..., hosts_permitidos=...)`.
  - Rotas: `GET /api/v1/casa?perfil=`, `/api/v1/resumo`, `/api/v1/rotas` (`{"inseguro": AnaliseDeRota, "seguro": AnaliseDeRota}`), `/api/v1/replay` (`{"inseguro": bool, "seguro": bool}`), `/api/v1/formigueiro/stream?perfil=&modo=&semente=&velocidade=`. **`/api/v1/perfil` some.** `modo=replay` sem arquivo → 404 `{"detail": "replay indisponível para este perfil"}`. O stream verifica o `asyncio.Event` do registro antes de cada snapshot e, se ele estiver marcado, emite `fim` e para.

- [ ] **Step 1: Testes que falham** em `test_api.py`, com `FonteFalsa` (snapshots fixos de `docs/demo/snapshots-exemplo.jsonl`, `replay` configurável, `analise` fixa) e `ResumoFalso`:

```python
def test_casa_por_perfil(): ...            # perfil=seguro → json["perfil"] == "seguro"
def test_resumo_traz_a_origem(): ...       # json["origem"] == "exemplo" e json["resumo"]["total_eventos"]
def test_rotas_dos_dois_perfis(): ...      # chaves inseguro/seguro; bloqueadas e riscos_por_no presentes
def test_replay_disponivel(): ...          # {"inseguro": True, "seguro": False} conforme a FonteFalsa
def test_stream_replay_usa_os_snapshots_gravados(): ...
def test_stream_replay_sem_arquivo_da_404(): ...
@pytest.mark.parametrize("q", ["perfil=xyz", "modo=xyz", "velocidade=10", "velocidade=0.1",
    "velocidade=nan", "velocidade=abc", "semente=-1", f"semente={2**31}"])
def test_limite_invalido_da_422_sem_rodar_a_fonte(q): ...
def test_parametros_do_aco_vindos_do_cliente_sao_ignorados(): ...  # ?iteracoes=1000&formigas=999 → a fonte recebe só (perfil, semente)
def test_o_stream_mais_novo_vence(): ...
    # RegistroDeStreams direto: abrir("a") duas vezes → o primeiro evento fica marcado, o segundo não;
    # abrir("b") não marca o de "a"
def test_stream_termina_com_fim(): ...
```

- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/painel/test_api.py -q` → FAIL (`painel.modelos` inexistente).
- [ ] **Step 3: Implementar** `modelos.py`, `streams.py`, as portas e as rotas. O cliente do registro é `request.client.host`.
- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → verde; `uv run lint-imports` → 3 contratos KEPT.
- [ ] **Step 5: Commit**: `feat(painel): adiciona portas, modelos e API da casa, rotas, resumo e replay`. Arquivos: os listados acima e a remoção de `tests/unit/painel/test_app.py`.

---

### Task 3: Adaptadores locais e análise da rota

**Files:**
- Modify: `src/honeyant/pathfinder/prever.py`, `src/honeyant/apps/local.py`
- Test: `tests/unit/pathfinder/test_prever.py` (novos casos), `tests/e2e/test_esqueleto.py` (atualizado)

**Interfaces:**
- Consumes: as portas e os modelos da Tarefa 2; `montar_grafo`, `bloqueada`, `Dijkstra`, `ACO`.
- Produces:
  - `pathfinder/prever.py`: `analisar_rota(perfil, evidencias, resumo, modelo=None) -> AnaliseDoGrafo`, com o dataclass `AnaliseDoGrafo(rota: Rota | None, riscos: dict[str, float], bloqueadas: list[str])`. `riscos` cobre **todas** as arestas não bloqueadas; `bloqueadas` usa `fraqueza.bloqueada` sobre as evidências combinadas, na ordem do perfil.
  - `apps/local.py`:
    - `FonteDasFixtures(casas, evidencias_por_perfil, resumo, demo_dir)` implementa `FonteDoFormigueiro`. `analise(perfil)` converte `AnaliseDoGrafo` em `AnaliseDeRota`: `riscos` só das arestas da rota; `riscos_por_no[n]` = maior risco entre as arestas que tocam `n` (0 se nenhuma). `replay(perfil)` lê `demo_dir/replay-<perfil>.jsonl` se existir, senão `None`.
    - `FonteDoResumoLocal(demo_dir)`: o `resumo-real-*.json` mais recente pelo nome; senão, o `resumo-congelado.json` com `origem="exemplo"`.
    - `montar(config, ...)` carrega os dois perfis e passa tudo a `criar_app`. `ConfigLocal.perfil` deixa de existir (o perfil agora vem da query); `HONEYANT_PERFIL` é removido do `de_ambiente`. Os testes de `tests/e2e/test_esqueleto.py` que montam `ConfigLocal(perfil=...)` passam a escolher o perfil pela query do stream.

- [ ] **Step 1: Testes que falham.**
  - Em `test_prever.py`: `test_analise_inseguro_sem_bloqueio_e_riscos_em_todas_as_arestas` (`bloqueadas == []`, 11 riscos em [0, 1]); `test_analise_seguro_bloqueia_camera_broker` (`bloqueadas == ["camera->broker"]`, que também não aparece em `riscos`); `test_aco_termina_na_rota_do_dijkstra` (parametrizado nos dois perfis: `ColetorDeSnapshots` + `ACO(ParametrosACO(semente=42))` → `snapshots[-1].melhor.nos == analisar_rota(...).rota.nos`).
  - Em `tests/e2e/test_esqueleto.py`: `test_e2e_rotas_e_razao` (`GET /api/v1/rotas`: inseguro passa pela câmera, seguro pelo roteador; a razão `inseguro.plausibilidade / seguro.plausibilidade` é igual a `exp(seguro.custo - inseguro.custo)` com `rel=1e-9`); `test_e2e_stream_por_perfil` (o último snapshot de `perfil=seguro` não passa pela câmera); `test_resumo_cai_no_exemplo_sem_arquivo_real` (`origem == "exemplo"`); `test_resumo_real_mais_recente_vence(tmp_path)` (com dois `resumo-real-*.json`, vale o de data maior).
- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/pathfinder/test_prever.py tests/e2e -q` → FAIL.
- [ ] **Step 3: Implementar** `analisar_rota` e os adaptadores.
- [ ] **Step 4: Rodar e ver passar**: `uv run pytest -m "not integration" -q && uv run lint-imports` → verde.
- [ ] **Step 5: Commit**: `feat(apps): implementa as portas do painel com fixtures, Dijkstra e resumo local`.

---

### Task 4: Estado do túnel, geometria e testes JS no CI

**Files:**
- Create: `src/honeyant/painel/static/js/package.json` (`{"type": "module"}`), `static/js/estado.js`, `static/js/geometria.js`, `static/layout.json`, `tests/js/estado.test.mjs`, `tests/js/geometria.test.mjs`
- Modify: `.github/workflows/ci.yml` (no job `qualidade`, depois dos testes Python: `- uses: actions/setup-node@v4` com `node-version: "20"`, e `- name: Testes JS` → `node --test tests/js/`)

**Interfaces:**
- Produces:
  - `estado.js`:
    - `estadoDoTunel(chave, snapshot, analise) -> {largura: number, brilho: number, rota: boolean, bloqueado: boolean}`. `largura = 4 + 18 · τ/τ_max` (τ ausente → 4); `brilho = τ/τ_max` (0 se ausente); `bloqueado = analise.bloqueadas.includes(chave)`; `rota` = a aresta está em `analise.rota.nos` (pares consecutivos).
    - `aceitarSnapshot(atual, novo) -> boolean`: aceita se `atual` é nulo ou se `novo.execucao_id === atual.execucao_id`. O front troca a execução corrente ao abrir um stream novo.
  - `geometria.js`:
    - `caminhoDoTunel(origem, destino, layout) -> [[x, y], ...]`: `[origem, ...layout.tuneis["a->b"], destino]` (sem entrada no layout, ligação direta).
    - `ehOrtogonal(caminho)`, `naGrade(caminho, grade = GRADE)`, `comprimento(caminho)`, `pontoNoCaminho(caminho, distancia) -> {x, y, dx, dy}` (direção do segmento atual).
    - `invadeEntrada(caminho, entrada, folga = FOLGA) -> boolean`: algum segmento passa a menos de `RAIO_ENTRADA + folga` do centro.
    - `sobreposicao(a, b, zonas = []) -> number`: comprimento em que segmentos colineares de `a` e `b` correm juntos, descontando o trecho dentro de `RAIO_ENTRADA + FOLGA` das entradas em `zonas` (pontas comuns).
    - `caixaDoRotulo(no, lado, texto) -> {x0, y0, x1, y1, x, y, ancora}` (lados: acima, abaixo, esquerda, direita e as quatro diagonais) e `cruzaCaixa(caminho, caixa, meia = 11) -> boolean`.
    - Exporta `GRADE = 10`, `RAIO_ENTRADA = 22`, `FOLGA = 12`.
  - `layout.json`: um par de pontos de controle por aresta dos perfis (as 11 arestas são as mesmas nos dois), ajustados à mão até o teste de folga passar. O caso que precisa de desvio é `roteador->broker`, que hoje passa sob a lâmpada.

- [ ] **Step 1: Testes que falham** (`node:test` + `node:assert/strict`; os perfis são lidos de `docs/demo/` com `fs`):

```js
test("largura proporcional ao feromônio", ...)       // τ = τ_max → 22; τ = τ_max/2 → 13; ausente → 4
test("aresta bloqueada vira cadeado", ...)           // bloqueadas ["camera->broker"] → bloqueado true
test("ausente do feromônio sem estar bloqueada não vira cadeado", ...)  // bloqueado false, largura 4
test("rota destacada", ...)                          // rota internet,camera,broker,fechadura → "camera->broker".rota true; "roteador->broker".rota false
test("snapshot de outra execução é recusado", ...)   // aceitarSnapshot({execucao_id:"a"},{execucao_id:"b"}) === false
test("túneis ortogonais e na grade", ...); test("nenhum túnel invade entrada fora dele", ...); test("nenhum túnel corre por cima de outro", ...); test("nenhum nome cruza túnel", ...)  // reais e de fundo, dois perfis
test("sem layout o teste de folga pega a lâmpada", ...)  // layout {} → roteador->broker invade "lampada" (prova que o teste morde)
```

- [ ] **Step 2: Rodar e ver falhar**: `node --test tests/js/` → FAIL (módulos inexistentes).
- [ ] **Step 3: Implementar** `estado.js` e `geometria.js` e ajustar o `layout.json` até a folga passar.
- [ ] **Step 4: Rodar e ver passar**: `node --test tests/js/` → todos os testes passam.
- [ ] **Step 5: Commit**: `feat(painel): adiciona estado do tunel, geometria com folga e testes JS no CI`.

---

### Task 5: Cena em grade e página

**Files:**
- Create: `static/js/cena.js`, `static/js/app.js`, `static/painel.css`, `static/icones.svg`
- Modify: `static/index.html`; remover `static/formigueiro.js` e `static/formigueiro.css`
- Test: `tests/unit/painel/test_static.py` (atualizado)

**Interfaces:**
- Consumes: `estadoDoTunel`, `aceitarSnapshot`, `caminhoDoTunel`, `pontoNoCaminho`, `caixaDoRotulo`, constantes (Tarefa 4); API (Tarefa 2).
- Produces:
  - `cena.js`: `criarCena(svg, casa, layout, {reduzido}) -> {aplicar(snapshot, analise), animar(agora), limpar(analise)}`. Desenha os túneis de fundo (`layout.decoracao`, uma vez), os túneis reais (base + miolo, cantos retos), as entradas (círculo com ícone; internet como meio-círculo na borda; fechadura quadrada com borda dupla), os nomes pelo `caixaDoRotulo`, as setas da rota e até 20 formigas (quadrados vermelhos) num único laço de `requestAnimationFrame`.
  - `app.js`: carrega `/api/v1/casa?perfil=inseguro`, `/api/v1/rotas`, `/static/layout.json`; controles ("Prever invasão", velocidade segmentada de 0,25× a 4×); um `EventSource` por vez (fecha o anterior antes de abrir); `aceitarSnapshot`; `aria-live="polite"` com "Rota prevista: Internet, Câmera, Broker, Fechadura. Ponto fraco: <origem> para <destino>." (ponto fraco = maior valor em `analise.riscos`); 401/403 → "Sessão expirada. Entre de novo."
  - `index.html`: cabeçalho (nome, selo "Vulnerável", espaço para o horário do resumo), barra de controles, `<svg id="formigueiro" viewBox="0 0 1000 640">`, `<aside id="lateral">` (vazio nesta entrega) e a legenda (túnel, formiga do ACO, formiga de ataque, rota prevista, túnel bloqueado, com forma **e** cor). `@media (max-width: 1180px)` coloca o lateral embaixo da cena.

- [ ] **Step 1: Carregar a skill `frontend-design:frontend-design`** e fixar a direção visual dentro da seção 4.7 do spec (grafite liso, túneis cinza-azulados apagados, formigas vermelhas, âmbar na rota, verde-azulado, fonte do sistema com `tabular-nums`).
- [ ] **Step 2: Testes que falham** em `test_static.py`:
  - `test_html_sem_inline` (todo `<script>` com `type="module"` e `src`; nenhum `style=`, `<style>` ou `on*`);
  - `test_todos_os_js_sem_api_proibida` (varre `static/js/*.js` contra a lista das Global Constraints);
  - `test_ids_usados_pelo_js_existem` (todo `getElementById("x")` de `app.js` tem `id="x"` no HTML);
  - `test_icones_cobrem_os_tipos` (todo `TipoDeNo` tem um `<symbol id="<tipo>">` em `icones.svg`);
  - `test_rotulo_hostil_sai_como_json` (o caso atual, agora via `/api/v1/casa`).
- [ ] **Step 3: Rodar e ver falhar**: `uv run pytest tests/unit/painel/test_static.py -q` → FAIL.
- [ ] **Step 4: Implementar** `cena.js`, `app.js`, `painel.css`, `icones.svg` e `index.html`.
- [ ] **Step 5: Rodar e ver passar**: `uv run pytest -m "not integration" -q && node --test tests/js/ && node --check src/honeyant/painel/static/js/*.js` → verde.
- [ ] **Step 6: Carregar a skill `anthropic-skills:impeccable`** e fazer a passada de crítica e polimento (contraste AA, hierarquia, foco visível, estados dos botões). Aplicar o que couber sem mudar as interfaces.
- [ ] **Step 7: Verificação visual (Lucas)**: `uv run honeyant-local` → `http://127.0.0.1:8000/`. Conferir:
  - em 1366×768: a rota pela câmera destacada e contínua, nenhum túnel sobre uma entrada alheia, nenhum rótulo sobre uma linha, formigas andando e o console sem erro de CSP;
  - em 1024×768 (ou zoom de 125%): sem rolagem horizontal;
  - com "reduzir movimento" do sistema ligado: nada anima.

  Prints para o README.
- [ ] **Step 8: Commit e PR da entrega 1**: `feat(painel): desenha o formigueiro em grade e a nova pagina`. Push de `feat/painel-cena` e PR (revisor Kawe).

---

## Entrega 2 — Mitigação animada e comparativo

### Task 6: Replay versionado

**Files:**
- Create: `src/honeyant/apps/gravar_replay.py`, `docs/demo/replay-inseguro.jsonl`, `docs/demo/replay-seguro.jsonl`, `tests/unit/apps/test_gravar_replay.py`
- Modify: `pyproject.toml` (`honeyant-gravar-replay = "honeyant.apps.gravar_replay:main"`)

**Interfaces:**
- Consumes: `GravadorDeReplay` (`pathfinder/adapters/replay.py`), `prever_rota`, `ACO`, `ParametrosACO(semente=42)`.
- Produces: `gerar_replays(demo_dir: Path) -> dict[TipoDePerfil, str]` (o conteúdo `.jsonl` em memória, via `GravadorDeReplay.serializar()`); `main()` grava `demo_dir/replay-<perfil>.jsonl` com `GravadorDeReplay.salvar`. O resumo usado é o mesmo da `FonteDoResumoLocal` (real se existir).

- [ ] **Step 1: Testes que falham**:
  - `test_replays_commitados_estao_atualizados`: para cada perfil, `gerar_replays(DEMO)[p] == (DEMO / f"replay-{p}.jsonl").read_text()`. Mensagem de falha: "rode `uv run honeyant-gravar-replay` e faça commit de `docs/demo/replay-*.jsonl`";
  - `test_replay_inseguro_termina_pela_camera` (o último snapshot passa pela câmera);
  - `test_main_grava_os_dois_arquivos(tmp_path)` (com as fixtures copiadas para `tmp_path`).
- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/apps/test_gravar_replay.py -q` → FAIL.
- [ ] **Step 3: Implementar** e rodar `uv run honeyant-gravar-replay` para gerar os dois arquivos.
- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → verde; `curl "http://127.0.0.1:8000/api/v1/replay"` com o painel de pé → `{"inseguro": true, "seguro": true}`.
- [ ] **Step 5: Commit**: `feat(apps): grava os replays da demo e trava os arquivos versionados no CI`.

### Task 7: Mitigação, desmoronamento, comparativo e Replay no front

**Files:**
- Create: `static/js/comparativo.js`, `tests/js/comparativo.test.mjs`, `tests/js/animacao.test.mjs`
- Modify: `static/js/app.js`, `static/js/cena.js`, `static/index.html`, `static/painel.css`

**Interfaces:**
- Consumes: Tarefas 4 e 5; `/api/v1/rotas`, `/api/v1/replay`, stream com `perfil` e `modo`.
- Produces:
  - `comparativo.js`: `formatarComparativo(antes: Rota, depois: Rota | null) -> {titulo: string, razao: number | null}`. Razão = `antes.plausibilidade / depois.plausibilidade`. Se razão ≥ 2: `"<arredondado>× menos plausível"`. Se 1 ≤ razão < 2: `"<round((1 − 1/razão)·100)>% menos plausível"`. Se `depois` é nulo: `"nenhuma rota até a fechadura"` com `razao: null`.
  - `cena.js`:
    - `planoDeAnimacao(reduzido: boolean) -> {formigas: boolean, desmoronamentoMs: number}`, que devolve `{true, 1200}` ou `{false, 0}`;
    - `desmoronar(chave)`: o túnel pisca, o tracejado se abre das pontas para o meio com entulho em quadradinhos, o cadeado aparece e as formigas daquele túnel somem (spec, 4.6).
  - `app.js`:
    - o botão "Aplicar mitigação (perfil seguro)" ↔ "Desfazer mitigação";
    - ao aplicar: `desmoronar("camera->broker")` → carrega `casa?perfil=seguro` → abre um stream novo → selo "Protegida" → mostra a nota;
    - ao desfazer: volta tudo;
    - o botão "Replay" usa `modo=replay` e fica desabilitado, com o motivo em `title` e texto, quando `/api/v1/replay` disser `false`;
    - o cartão "Antes e depois" no `#lateral` mostra as duas rotas, os dois custos e `titulo` em destaque.

- [ ] **Step 1: Testes JS que falham**:
  - `comparativo.test.mjs`: com as plausibilidades `e^-1.422` e `e^-4.856`, a razão é igual a `exp(4.856 − 1.422)` (tolerância 1e-9) e o título é `"31× menos plausível"`; com a razão 1,5, o título é `"33% menos plausível"`; com `depois` nulo, `"nenhuma rota até a fechadura"`;
  - `animacao.test.mjs`: `planoDeAnimacao(true)` devolve `{formigas: false, desmoronamentoMs: 0}`, e `planoDeAnimacao(false)` devolve `{formigas: true, desmoronamentoMs: 1200}`.
- [ ] **Step 2: Rodar e ver falhar**: `node --test tests/js/` → FAIL.
- [ ] **Step 3: Implementar** (carregar `frontend-design` antes do CSS do cartão e do desmoronamento).
- [ ] **Step 4: Rodar e ver passar**: `node --test tests/js/ && uv run pytest -m "not integration" -q` → verde.
- [ ] **Step 5: Verificação visual (Lucas)**:
  - aplicar → o túnel câmera→broker desmorona, a rota passa pelo roteador e o cartão mostra a razão;
  - desfazer → volta;
  - Replay → mesma história sem o ACO;
  - com "reduzir movimento": tudo vai direto ao estado final.
- [ ] **Step 6: Commit e PR da entrega 2**: `feat(painel): anima a mitigacao e mostra o comparativo antes e depois`. Push de `feat/painel-mitigacao` e PR (revisor Kawe).

---

## Entrega 3 — Painel lateral com os dados da isca

> **Antes da Tarefa 8:** perguntar ao Lucas se a prova real (twin + capturas `.pcap`) está encaminhada. Se não estiver, **parar** e avisar (spec, seção 8).

### Task 8: Resumo real exportado da isca

**Files:**
- Create: `src/honeyant/intel/resumo.py`, `src/honeyant/apps/exportar_resumo.py`, `tests/unit/intel/test_resumo.py`, `tests/unit/apps/test_exportar_resumo.py`, `docs/demo/resumo-real-AAAA-MM-DD.json` (gerado na EC2)
- Modify: `src/honeyant/intel/adapters/sqlite_leitura.py`, `pyproject.toml` (`honeyant-exportar-resumo = "honeyant.apps.exportar_resumo:main"`), `tests/unit/core/test_fixtures_demo.py`, `infra/aws/DEPLOY.md`

**Interfaces:**
- Consumes: `LeitorSqlite` (Plano 2), `EventoDeAtaque`, `ResumoDeAmeaca`.
- Produces:
  - `LeitorSqlite.eventos_desde(inicio: datetime) -> list[EventoDeAtaque]`: lê a coluna `dados` com `ts >= inicio`.
  - `intel/resumo.py`: `agregar(eventos: Iterable[EventoDeAtaque], acumulado: Mapping[Servico, int], agora: datetime, janela_horas: int = 24) -> ResumoDeAmeaca`. Regras:
    - considera só os eventos com `ts > agora − janela`;
    - `pais` nulo vira `"ZZ"` e `asn` nulo vira `0`;
    - `intencao = {}` (o fuzzy de intenção é do `intel` futuro);
    - `top_credenciais`: as 20 mais frequentes, só eventos com `usuario` ou `senha`; empate decidido por `(usuario, senha)` em ordem crescente, para ser determinístico;
    - `gerado_em = agora`.
  - `apps/exportar_resumo.py`: `main()` lê `HONEYANT_DB` (padrão `/dados/isca.db`). Sem argumento, imprime o JSON na saída padrão; com `destino`, grava o arquivo.

- [ ] **Step 1: Testes que falham**:
  - `test_resumo.py`:
    - `test_agrega_contagens_paises_e_credenciais`;
    - `test_eventos_fora_da_janela_ficam_de_fora`;
    - `test_janela_vazia_da_resumo_valido_com_total_zero` (Review Focus 2);
    - `test_desempate_deterministico`;
    - `test_nenhum_ip_no_resumo`: os eventos usam `203.0.113.7` e `2001:db8::1`; o `model_dump_json()` não contém nenhum dos dois.
  - `test_exportar_resumo.py`: `test_exporta_do_sqlite_de_teste` (grava com `RepositorioSqlite`, roda `main` com `HONEYANT_DB` e um destino em `tmp_path`, valida com `ResumoDeAmeaca` e confere que não há IP no texto).
- [ ] **Step 2: Rodar e ver falhar**: `uv run pytest tests/unit/intel tests/unit/apps/test_exportar_resumo.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar e ver passar**: o mesmo comando → verde.
- [ ] **Step 5: Gerar o resumo real na EC2 (Lucas).** Atualizar o código (`git fetch && git checkout <branch>`, depois `docker compose -f infra/compose.cloud.yml build isca`, com a janela de saída aberta só durante o build) e rodar:
  ```bash
  docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml run --rm -T --entrypoint honeyant-exportar-resumo verificar-ro > resumo-real.json
  ```
  Copiar para o PC (`scp`) como `docs/demo/resumo-real-<AAAA-MM-DD>.json`. Registrar o comando numa seção "Exportar o resumo real" do `DEPLOY.md`.
- [ ] **Step 6: Trava da demo com o resumo real**: em `test_fixtures_demo.py`, adicionar:
  - `test_resumo_real_valido_e_tem_credencial` (o resumo real mais recente valida, e `top_credenciais[0]` tem `usuario` e `senha` não nulos: é a senha da câmera no perfil inseguro, por decisão de 06/11);
  - `test_rotas_da_demo_com_o_resumo_real` (Dijkstra: inseguro pela câmera, seguro pelo roteador).

  Se o segundo falhar, **parar e avisar o Lucas** antes de calibrar qualquer fixture. Regenerar os replays (`uv run honeyant-gravar-replay`), porque o resumo em uso mudou.
- [ ] **Step 7: Rodar tudo**: `uv run pytest -m "not integration" -q && node --test tests/js/` → verde.
- [ ] **Step 8: Commit**: `feat(intel): agrega e exporta o resumo real da isca sem IPs`. Arquivos: os desta tarefa, mais `docs/demo/replay-*.jsonl` regenerados.

### Task 9: Cartões da isca, da rota e dos dispositivos e formigas de ataque

**Files:**
- Create: `static/js/risco.js`, `tests/js/risco.test.mjs`
- Modify: `static/js/app.js`, `static/js/cena.js`, `static/index.html`, `static/painel.css`, `tests/unit/painel/test_static.py`

**Interfaces:**
- Consumes: `/api/v1/resumo`, `/api/v1/rotas`, `/api/v1/casa`.
- Produces:
  - `risco.js`:
    - `nivelDeRisco(r: number) -> "baixo" | "medio" | "alto" | "critico"` (faixas das Global Constraints);
    - `sortearServico(porServico: object, aleatorio: () => number) -> string`: proporcional, com o gerador injetado para o teste.
  - `cena.js`: `soltarAtaque(servico)`: quadrado vermelho de 9 px com contorno claro, que entra pela entrada da internet.
  - `app.js`:
    - **"Ataques reais"**: título com a origem ("Ataques reais, congelados em <data>" ou "Dados de exemplo"); total; barra por serviço; top 5 senhas como `usuario / senha`; top 5 países. Com `total_eventos = 0`: "nenhum ataque nas últimas 24 h";
    - **"Rota prevista"**: os passos numerados e o ponto fraco com ícone **e** texto;
    - **"Dispositivos na rede"**: tipo, categoria (por enquanto, o tipo) e `nivelDeRisco(riscos_por_no[id])`;
    - o horário do resumo vai para o cabeçalho;
    - uma formiga de ataque a cada 2 s, com `sortearServico`, e a nota "ritmo baseado nos ataques congelados em <data>". Isso fica desligado com `prefers-reduced-motion`.

- [ ] **Step 1: Testes que falham**:
  - `risco.test.mjs`: as faixas (0,29 → baixo; 0,3 → médio; 0,6 → alto; 0,85 → crítico) e `sortearServico({telnet: 198, mqtt: 2}, () => 0.995)` igual a `"mqtt"` (e com `0.5`, igual a `"telnet"`);
  - `test_static.py`: `test_senha_hostil_do_resumo_sai_limpa_e_como_json` (Review Focus 3). Um `ResumoFalso` com a senha `"<img src=x onerror=alert(1)>\x07" + "a" * 100` chega em `/api/v1/resumo` sem o `\x07`, com no máximo 64 caracteres e com o `<img` intacto como texto JSON. O JS só usa `textContent`, e isso já está coberto pela varredura.
- [ ] **Step 2: Rodar e ver falhar**: `node --test tests/js/ && uv run pytest tests/unit/painel/test_static.py -q` → FAIL.
- [ ] **Step 3: Implementar** (carregar `frontend-design` antes dos cartões e `impeccable` no fim).
- [ ] **Step 4: Rodar e ver passar**: `node --test tests/js/ && uv run pytest -m "not integration" -q` → verde.
- [ ] **Step 5: Verificação visual (Lucas)**: os cartões com os dados reais, as formigas de ataque entrando, a origem dos dados visível e o leitor de tela lendo a rota. Prints para o README e os slides.
- [ ] **Step 6: Commit e PR da entrega 3**: `feat(painel): mostra os ataques reais, a rota e os dispositivos no painel lateral`. Push de `feat/painel-isca` e PR (revisores Kawe e Rafael).

---

## Ao terminar cada entrega

Revisão crítica no PR, como o briefing pede (seção 8): pontos fortes, fracos, riscos, escalabilidade, segurança, melhorias, dívida técnica e notas de 0 a 10 para arquitetura, segurança e escalabilidade, com os prints.

## Fora deste plano

- Entregas 4 e 5 (dispositivos novos), num plano próprio, se houver tempo depois de 07/11.
- Login (PR do Gustavo, encaixado pela Tarefa 1); TLS e o painel na EC2; o `intel` ao vivo; o `honeyant mitigar` real; o desvio automático dos túneis.
