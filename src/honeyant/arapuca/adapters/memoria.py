"""Repositório em memória, usado nos testes."""

from collections import Counter
from datetime import datetime

from honeyant.arapuca.ports import RETENCAO, TETO_EVENTOS
from honeyant.core.eventos import EventoDeAtaque, Servico


class RepositorioEmMemoria:
    def __init__(self, teto_eventos: int = TETO_EVENTOS) -> None:
        self._teto = teto_eventos
        self._eventos: list[EventoDeAtaque] = []
        self._acumulado: Counter[Servico] = Counter()

    def salvar(self, evento: EventoDeAtaque) -> None:
        self._eventos.append(evento)
        self._acumulado[evento.servico] += 1

    def contar(self) -> int:
        return len(self._eventos)

    def acumulado_por_servico(self) -> dict[Servico, int]:
        return dict(self._acumulado)

    def aplicar_limites(self, agora: datetime) -> int:
        antes = len(self._eventos)
        limite = agora - RETENCAO
        restantes = sorted((e for e in self._eventos if e.ts >= limite), key=lambda e: e.ts)
        self._eventos = restantes[-self._teto :] if len(restantes) > self._teto else restantes
        return antes - len(self._eventos)
