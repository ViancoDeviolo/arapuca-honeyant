"""Limitador de conexões: simultâneas (total e por IP) e taxa por IP."""

import time
from collections import Counter, deque
from collections.abc import Callable

_JANELA_S = 60.0


class Limitador:
    def __init__(
        self,
        max_total: int = 200,
        max_por_ip: int = 4,
        taxa_por_minuto: int = 20,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_total = max_total
        self._max_por_ip = max_por_ip
        self._taxa = taxa_por_minuto
        self._relogio = relogio
        self._ativas: Counter[str] = Counter()
        self._chegadas: dict[str, deque[float]] = {}

    def entrar(self, ip: str) -> bool:
        agora = self._relogio()
        self._esquecer_inativos(agora)
        chegadas = self._chegadas.setdefault(ip, deque())
        if (
            sum(self._ativas.values()) >= self._max_total
            or self._ativas[ip] >= self._max_por_ip
            or len(chegadas) >= self._taxa
        ):
            if not chegadas and not self._ativas[ip]:
                del self._chegadas[ip]
            return False
        chegadas.append(agora)
        self._ativas[ip] += 1
        return True

    def sair(self, ip: str) -> None:
        if self._ativas[ip] > 0:
            self._ativas[ip] -= 1
        if self._ativas[ip] == 0:
            del self._ativas[ip]

    def ips_rastreados(self) -> int:
        """Quantos IPs o limitador guarda em memória (para provar que não cresce sem limite)."""
        return len(self._chegadas)

    def _esquecer_inativos(self, agora: float) -> None:
        for ip in list(self._chegadas):
            chegadas = self._chegadas[ip]
            while chegadas and agora - chegadas[0] >= _JANELA_S:
                chegadas.popleft()
            if not chegadas and not self._ativas[ip]:
                del self._chegadas[ip]
