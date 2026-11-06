# Correção do pathfinder (replay + ADRs)

## O que aconteceu nas suas branches

O pathfinder (fuzzy, ACO, Dijkstra e snapshots) **já está na `main`**, desde o PR #4. As branches
`feat/pathfinder-adr-replay`, `feat/pathfinder-fuzzy-aco` e `feat/reinicializacao-limpa` tentavam
refazer esse trabalho por cima e acabaram quebrando o CI:

- marcas de conflito de merge (`<<<<<<<`, `=======`) ficaram no `ports.py`;
- uma segunda cópia do pathfinder em `pathfinder/dominio/`, com outra API;
- o `pyproject.toml` foi substituído e perdeu as configurações do ruff, pytest, bandit e
  import-linter, além da dependência `pydantic`; o `uv.lock` ficou desatualizado;
- arquivos `__pycache__/*.pyc` e `honeyant.egg-info` foram commitados;
- o job de segurança do CI (gitleaks e pip-audit) foi removido. Ele **precisa** existir.

Não há o que salvar dessas branches além do gravador de replay e dos ADRs, que foram refeitos aqui
sobre a `main` atual.

## O que vem neste pacote

| Arquivo | O que é |
|---|---|
| `src/honeyant/pathfinder/adapters/__init__.py` | pacote dos adaptadores do pathfinder |
| `src/honeyant/pathfinder/adapters/replay.py` | `GravadorDeReplay`: Observer que grava os snapshots do ACO num `.jsonl`, de forma atômica |
| `tests/unit/pathfinder/test_replay.py` | 9 testes: um snapshot por iteração, determinismo byte a byte, casa insegura passa pela câmera, casa segura não, gravação atômica |
| `docs/adr/0005-custo-da-aresta-e-fuzzy.md` | ADR do fuzzy e do custo −ln(risco), alinhado ao código da `main` |
| `docs/adr/0006-aco-com-dijkstra-gabarito.md` | ADR do ACO com Dijkstra como gabarito e a medição dos parâmetros |

Os ADRs usam os números 0005 e 0006 porque essa é a ordem prevista no spec (seção 18). Os antigos
`0007`, `0008`, `pathfinder-01` e `pathfinder-02` ficaram de fora: os dois últimos descreviam a versão
descartada (custo = 1 − risco, ρ = 0,3, q = 0,1), que não é o que está no código.

Verificado sobre a `main`: ruff, formatação, import-linter (3 contratos mantidos), bandit sem achados
e 166 testes passando.

## Passo a passo

1. Atualizar a `main` e criar uma branch nova a partir dela:
   ```powershell
   git switch main
   git pull
   git switch -c feat/pathfinder-replay
   ```
2. Copiar as pastas `src`, `tests` e `docs` deste pacote para a raiz do repositório
   (elas só **adicionam** arquivos; nenhum arquivo existente é alterado).
3. Conferir que só os 5 arquivos aparecem:
   ```powershell
   git status
   ```
4. Rodar o CI localmente:
   ```powershell
   uv sync --locked --all-extras
   uv run ruff check .
   uv run ruff format --check .
   uv run lint-imports
   uv run pytest -m "not integration"
   ```
5. Commitar e enviar:
   ```powershell
   git add src/honeyant/pathfinder/adapters tests/unit/pathfinder/test_replay.py docs/adr/0005-custo-da-aresta-e-fuzzy.md docs/adr/0006-aco-com-dijkstra-gabarito.md
   git commit -m "feat(pathfinder): adiciona gravador de replay em jsonl e ADRs 0005 e 0006"
   git push -u origin feat/pathfinder-replay
   ```
6. Abrir o PR para a `main` e pedir revisão ao Gustavo.

## Depois do merge

Fechar sem mergear os PRs antigos e apagar as branches `feat/pathfinder-adr-replay`,
`feat/pathfinder-fuzzy-aco` e `feat/reinicializacao-limpa`, para ninguém mergear uma delas por engano.

## Para não repetir

- Sempre começar uma branch a partir da `main` atualizada (`git pull` antes).
- Nunca usar `git add .` sem olhar o `git status`: é assim que `.pyc` e `egg-info` entram.
- Se o CI falhar, corrigir a causa; não remover etapas do `ci.yml`.
- Marcas `<<<<<<<` no código significam conflito não resolvido: nunca commitar com elas.
