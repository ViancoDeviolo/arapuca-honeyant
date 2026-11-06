"""Portas do pathfinder (padrões Strategy e Observer)."""

from typing import Protocol

from honeyant.core.rota import Rota, Snapshot
from honeyant.pathfinder.grafo import GrafoDeRisco


class AlgoritmoDeRota(Protocol):
    """Strategy: ACO e Dijkstra são trocáveis para quem pede a rota."""

    def calcular(self, grafo: GrafoDeRisco, origem: str, alvo: str) -> Rota | None:
        """Melhor rota de `origem` até `alvo`, ou `None` se não houver caminho."""
        ...


class ObservadorDeIteracao(Protocol):
    """Observer: recebe um snapshot por iteração do ACO (SSE, arquivo de replay...)."""

    def notificar(self, snapshot: Snapshot) -> None: ...
