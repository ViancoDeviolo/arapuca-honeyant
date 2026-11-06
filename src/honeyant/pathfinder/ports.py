<<<<<<< HEAD
"""Portas (interfaces) do pathfinder.

O domínio do ACO só conhece estas interfaces. Quem decide se o snapshot vai
para um arquivo JSON, para o painel via SSE ou para lugar nenhum é o adaptador.
"""

from __future__ import annotations

from typing import Protocol

from honeyant.pathfinder.dominio.snapshot import Snapshot


class ObservadorDeIteracao(Protocol):
    """Padrão Observer: é avisado a cada iteração, sem o ACO saber quem escuta."""

    def ao_iterar(self, snapshot: Snapshot) -> None: ...
=======
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
>>>>>>> 3d7260d40985afc72842049bf18cbcad320dfbb8
