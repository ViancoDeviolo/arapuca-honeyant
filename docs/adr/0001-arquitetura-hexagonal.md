# ADR 0001 — Arquitetura hexagonal, regra de dependência e composition root

- **Status:** aceito
- **Data:** 2026-11-05

## Contexto

Cinco pessoas trabalham em módulos diferentes (isca, intel, twin, sensor, pathfinder,
painel) com prazo curto. Sem uma regra clara, um módulo passa a importar o outro, os
contratos ficam espalhados e uma mudança em um quebra todos.

## Decisão

- **`core`** guarda só os contratos (Pydantic): `EventoDeAtaque`, `ResumoDeAmeaca`,
  `PerfilDaCasa`, `EvidenciaDeRede`, `Rota`, `Snapshot`. Não importa nenhum módulo.
- **Módulos** dependem só do `core` e **não importam uns aos outros**. O que vem de fora
  entra por **portas** (`Protocol`): `FonteDeEventos` (intel), `FonteDeTrafego` (sensor),
  `FonteDoFormigueiro` e `FonteDoResumo` (painel), `ObservadorDeIteracao` (pathfinder).
- **`apps/`** é o *composition root*: só ele monta os módulos e implementa as portas com
  adaptadores reais (arquivos, Docker, SQLite).
- O **import-linter** verifica as três regras no CI (`pyproject.toml`, `[tool.importlinter]`).

## Alternativas consideradas

- **Pacote único sem camadas:** mais rápido no primeiro dia, mas cada colega mexeria em
  tudo. Descartado.
- **Microsserviços:** isolamento real, mas custo de rede, deploy e contrato HTTP grande
  demais para o prazo. Descartado.

## Consequências

- Trocar uma fonte é escrever um adaptador: PostgreSQL no lugar do SQLite, interface de
  rede ao vivo no lugar do `.pcap`, intel ao vivo no lugar do resumo congelado.
- Testes unitários usam portas falsas sem Docker nem rede.
- Há algum código repetido de propósito (o SQL do esquema da isca aparece também no
  leitor do intel), porque um módulo não importa o outro.
