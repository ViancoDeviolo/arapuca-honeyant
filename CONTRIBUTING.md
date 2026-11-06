# Como contribuir

## Ambiente

1. Instale o [uv](https://docs.astral.sh/uv/).
2. Na raiz do repositório: `uv sync` (cria o `.venv` com Python 3.12 e as dependências do `uv.lock`).

## Antes de abrir um PR

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pytest
```

O CI roda esses comandos (e verificações de segurança) em todo PR. PR com CI vermelho não entra.

## Fluxo de trabalho

1. Crie uma branch a partir da `main` atualizada: `git switch -c feat/<modulo>-<assunto>`.
2. Escreva o teste primeiro, veja falhar, implemente, veja passar.
3. Commits pequenos, com mensagem em português no formato `tipo(escopo): descrição`.
   Tipos: `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`.
4. Abra o PR para a `main` e peça revisão de quem **consome** o seu módulo:

   | Módulo | Revisor |
   |---|---|
   | `core` (contratos) | toda a equipe |
   | `arapuca` | dono do `intel` |
   | `intel`, `sensor` | dono do `pathfinder` |
   | `twin` | dono do `arapuca` |
   | `pathfinder` | dono do `painel` |
   | `painel` | dono do `twin` |

5. Merge só com CI verde e uma aprovação.

## Regras de arquitetura

- `honeyant.core` não importa nenhum outro módulo do projeto.
- Módulos (`arapuca`, `intel`, `twin`, `sensor`, `pathfinder`, `painel`) **não importam uns aos outros**: conversam pelos contratos de `core`.
- Só `honeyant.apps` (composition root) junta vários módulos.

O `lint-imports` verifica essas regras no CI.

## Segurança

- Nunca commite segredos, `.env`, certificados ou bancos de dados (o `.gitignore` já cobre).
- Todo dado vindo da isca é hostil: valide e trunque antes de guardar; escape antes de exibir.
- Não use `git add .`: adicione os arquivos pelo nome.
