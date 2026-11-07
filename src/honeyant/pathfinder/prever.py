"""Caso de uso "prever invasão": evidências + perfil + resumo → rota (spec, seções 8 e 9)."""

from collections.abc import Iterable
from dataclasses import dataclass

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Rota, Snapshot
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.fraqueza import bloqueada
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


@dataclass(frozen=True)
class AnaliseDoGrafo:
    """Rota oficial (Dijkstra) e o risco de cada aresta, para o painel explicar a rota."""

    rota: Rota | None
    riscos: dict[str, float]  # todas as arestas não bloqueadas
    bloqueadas: list[str]  # bloqueadas pelas evidências, na ordem do perfil


def analisar_rota(
    perfil: PerfilDaCasa,
    evidencias: Iterable[EvidenciaDeRede],
    resumo: ResumoDeAmeaca,
    modelo: ModeloDeRisco | None = None,
) -> AnaliseDoGrafo:
    """Mesma regra do `montar_grafo`; a rota é a do Dijkstra (exata, spec do painel 3.2)."""
    combinadas = combinar_evidencias(evidencias)
    grafo = montar_grafo(perfil, combinadas, resumo, modelo or ModeloDeRisco())
    return AnaliseDoGrafo(
        rota=Dijkstra().calcular(grafo, perfil.origem, perfil.alvo),
        riscos={c: grafo.risco(c) for c in sorted(grafo.chaves())},
        bloqueadas=[a.chave for a in perfil.arestas if bloqueada(combinadas.get(a.chave))],
    )


class ColetorDeSnapshots:
    """Observer que guarda os snapshots em memória (o painel os transmite por SSE).

    Não é o gravador de replay: esse grava `.jsonl` e fica em `pathfinder/adapters/`.
    """

    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []

    def notificar(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)
