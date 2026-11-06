"""Portas (interfaces) do módulo arapuca."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.core.eventos import EventoDeAtaque, Servico

RETENCAO = timedelta(days=7)
TETO_EVENTOS = 200_000
TETO_BYTES = 200 * 1024 * 1024


class RepositorioDeEventos(Protocol):
    """Persistência dos eventos da isca (padrão Repository)."""

    def salvar(self, evento: EventoDeAtaque) -> None: ...

    def contar(self) -> int: ...

    def acumulado_por_servico(self) -> dict[Servico, int]:
        """Contador monotônico desde o início; a retenção nunca o reduz."""
        ...

    def aplicar_limites(self, agora: datetime) -> int:
        """Aplica retenção e tetos; devolve quantos eventos removeu."""
        ...


@dataclass
class Captura:
    """O que um serviço falso extraiu de uma sessão (sem IP nem horário)."""

    usuario: str | None = None
    senha: str | None = None
    comandos: list[str] = field(default_factory=list)
    bytes_recebidos: int = 0


Escrever = Callable[[bytes], Awaitable[None]]


class ServicoFalso(Protocol):
    """Um protocolo simulado pela isca (padrão Strategy). Nunca executa nada."""

    servico: Servico

    async def atender(self, leitor: LeitorLimitado, escrever: Escrever) -> Captura:
        """Conduz a sessão e devolve o que capturou. Nunca lança exceção."""
        ...


class ResolvedorGeo(Protocol):
    """País (ISO alfa-2) e ASN de um IP, a partir de base offline."""

    def resolver(self, ip: str) -> tuple[str | None, int | None]: ...
