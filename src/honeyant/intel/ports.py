"""Portas do intel: de onde vêm os eventos que ele agrega."""

from typing import Protocol

from honeyant.core.eventos import Servico


class FonteDeEventos(Protocol):
    """Leitura dos eventos da isca. O intel nunca escreve no banco."""

    def contar(self) -> int: ...

    def acumulado_por_servico(self) -> dict[Servico, int]: ...
