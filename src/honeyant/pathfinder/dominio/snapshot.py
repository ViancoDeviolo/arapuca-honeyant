"""Snapshot do ACO: o estado de uma iteração, pronto para ser observado.

PROVISÓRIO: o contrato oficial do snapshot vai para `honeyant.core` e precisa
ser combinado com o Gustavo (painel) e aprovado pelo Lucas. Até lá, esta
classe é só local ao pathfinder e não é importada por nenhum outro módulo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    """Foto do ACO ao fim de uma iteração (só dados necessários, nada da isca)."""

    iteracao: int
    # (origem, destino, feromônio) para cada aresta não bloqueada, em ordem fixa.
    feromonio: tuple[tuple[str, str, float], ...]
    # Caminhos das formigas que chegaram à fechadura (limitados em quantidade).
    caminhos: tuple[tuple[str, ...], ...]
    melhor_rota: tuple[str, ...] | None
    melhor_custo: float | None
