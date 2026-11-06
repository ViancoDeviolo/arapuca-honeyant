"""Portas do painel: de onde vêm os dados que ele desenha."""

from collections.abc import Sequence
from typing import Protocol

from honeyant.core.rota import Snapshot


class FonteDoFormigueiro(Protocol):
    """Quem roda o ACO. O painel só sabe pedir os snapshots de uma execução."""

    def snapshots(self, semente: int) -> Sequence[Snapshot]: ...
