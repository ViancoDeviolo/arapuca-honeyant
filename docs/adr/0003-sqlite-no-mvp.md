# ADR 0003 — SQLite no MVP (em vez de PostgreSQL) e leitura em `mode=ro`

- **Status:** aceito
- **Data:** 2026-11-05

## Contexto

A isca grava algumas centenas a poucos milhares de eventos por dia numa t3.micro (1 GB de
RAM). Quem lê (intel, exportação do resumo) não pode, em hipótese alguma, alterar o banco
da isca.

## Decisão

- **SQLite em modo WAL**, num volume da EC2. A isca é a **única escritora**.
- O acesso fica atrás do padrão **Repository** (`RepositorioSqlite` na isca, `LeitorSqlite`
  no intel).
- Quem lê usa **duas camadas** contra escrita: a URI `file:...?mode=ro` e um usuário de
  container sem permissão de escrita no arquivo. O `honeyant-verificar-ro` prova as duas
  na EC2 (resultado de 06/11 em `infra/aws/DEPLOY.md`).
- Teto de 200.000 eventos ou 200 MB, e retenção de 7 dias (LGPD).

## Alternativas consideradas

- **PostgreSQL:** paridade com produção e usuários com permissão de leitura nativos, mas
  mais um serviço, mais memória e mais superfície na mesma máquina da isca. Descartado
  para o MVP.

## Consequências

- Um único arquivo para copiar, inspecionar e apagar.
- Migrar para PostgreSQL é escrever outro adaptador do Repository, sem mudar o intel.
- Não escala para várias iscas escrevendo no mesmo banco (fora do escopo).
