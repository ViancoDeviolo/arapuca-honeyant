"""Caso de uso "prever invasão": evidências + perfil + resumo → rota (spec, seções 8 e 9)."""

from collections.abc import Iterable

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Rota, Snapshot
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import montar_grafo
from honeyant.pathfinder.ports import AlgoritmoDeRota


def prever_rota(
    perfil: PerfilDaCasa,
    evidencias: Iterable[EvidenciaDeRede],
    resumo: ResumoDeAmeaca,
    algoritmo: AlgoritmoDeRota,
    modelo: ModeloDeRisco | None = None,
) -> Rota | None:
    """Rota mais plausível da internet até a fechadura, ou `None` se não houver caminho."""
    grafo = montar_grafo(perfil, combinar_evidencias(evidencias), resumo, modelo or ModeloDeRisco())
    return algoritmo.calcular(grafo, perfil.origem, perfil.alvo)


class ColetorDeSnapshots:
    """Observer que guarda os snapshots em memória (o painel os transmite por SSE).

    Não é o gravador de replay: esse grava `.jsonl` e fica em `pathfinder/adapters/`.
    """

    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []

    def notificar(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)
