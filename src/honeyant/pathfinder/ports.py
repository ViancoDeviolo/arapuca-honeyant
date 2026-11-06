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
