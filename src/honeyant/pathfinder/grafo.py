"""Grafo de risco: a casa com um risco (0–1) e um custo em cada aresta não bloqueada."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.comum import chave_aresta
from honeyant.core.evidencia import EvidenciaDeRede
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.pathfinder.fraqueza import bloqueada, fraqueza, frequencia
from honeyant.pathfinder.fuzzy import ModeloDeRisco, custo_da_aresta


@dataclass(frozen=True)
class ArestaPonderada:
    origem: str
    destino: str
    risco: float
    custo: float = field(init=False)

    def __post_init__(self) -> None:
        if not (0 <= self.risco <= 1):
            raise ValueError(f"risco fora de [0, 1]: {self.risco!r}")
        object.__setattr__(self, "custo", custo_da_aresta(self.risco))

    @property
    def chave(self) -> str:
        return chave_aresta(self.origem, self.destino)


class GrafoDeRisco:
    """Lista de adjacência dirigida. Só contém arestas que um atacante consegue usar."""

    def __init__(self, arestas: Iterable[ArestaPonderada]) -> None:
        self._por_chave = {a.chave: a for a in arestas}
        self._saidas: dict[str, list[ArestaPonderada]] = {}
        for a in self._por_chave.values():
            self._saidas.setdefault(a.origem, []).append(a)

    def saidas(self, no: str) -> list[ArestaPonderada]:
        return self._saidas.get(no, [])

    def chaves(self) -> set[str]:
        return set(self._por_chave)

    def risco(self, chave: str) -> float:
        return self._por_chave[chave].risco

    def custo(self, chave: str) -> float:
        return self._por_chave[chave].custo


def montar_grafo(
    perfil: PerfilDaCasa,
    evidencias: Mapping[str, EvidenciaDeRede],
    resumo: ResumoDeAmeaca,
    modelo: ModeloDeRisco,
) -> GrafoDeRisco:
    """Aplica fraqueza → fuzzy → custo em cada aresta do perfil.

    `evidencias` já combinadas por aresta (`combinar_evidencias`).
    """
    arestas = []
    for a in perfil.arestas:
        evid = evidencias.get(a.chave)
        if bloqueada(evid):
            continue
        w = a.fraqueza_fixa if a.fraqueza_fixa is not None else fraqueza(evid)
        r = modelo.risco(frequencia(resumo, a.servico), w, a.exposicao)
        arestas.append(ArestaPonderada(a.origem, a.destino, r))
    return GrafoDeRisco(arestas)
