"""Portas do painel: de onde vêm os dados que ele desenha (spec, seção 3.2)."""

from collections.abc import Sequence
from typing import Protocol

from honeyant.core.casa import TipoDePerfil
from honeyant.core.rota import Snapshot
from honeyant.painel.modelos import AnaliseDeRota, ResumoComOrigem


class FonteDoFormigueiro(Protocol):
    """Quem roda o pathfinder para um perfil da casa."""

    def snapshots(self, perfil: TipoDePerfil, semente: int) -> Sequence[Snapshot]: ...

    def replay(self, perfil: TipoDePerfil) -> Sequence[Snapshot] | None:
        """Snapshots gravados (plano B offline), ou `None` se não houver arquivo."""
        ...

    def analise(self, perfil: TipoDePerfil) -> AnaliseDeRota:
        """Rota oficial (Dijkstra, exata)."""
        ...


class FonteDoResumo(Protocol):
    def resumo(self) -> ResumoComOrigem: ...
