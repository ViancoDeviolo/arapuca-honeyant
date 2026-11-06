import math

import pytest

from honeyant.core.rota import Algoritmo
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.grafo import ArestaPonderada, GrafoDeRisco


def _grafo(*arestas: tuple[str, str, float]) -> GrafoDeRisco:
    return GrafoDeRisco([ArestaPonderada(o, d, risco) for o, d, risco in arestas])


def test_escolhe_o_caminho_de_menor_custo():
    # a->b->d: 0.9*0.9 = 0.81 ; a->c->d: 0.95*0.5 = 0.475 ; a->d direto: 0.3
    g = _grafo(("a", "b", 0.9), ("b", "d", 0.9), ("a", "c", 0.95), ("c", "d", 0.5), ("a", "d", 0.3))
    r = Dijkstra().calcular(g, "a", "d")
    assert r.nos == ["a", "b", "d"]
    assert r.algoritmo is Algoritmo.DIJKSTRA
    assert r.plausibilidade == pytest.approx(0.81)
    assert r.custo == pytest.approx(-2 * math.log(0.9))


def test_sem_rota_devolve_none():
    g = _grafo(("a", "b", 0.9), ("c", "d", 0.9))
    assert Dijkstra().calcular(g, "a", "d") is None


def test_respeita_direcao():
    g = _grafo(("b", "a", 0.9))
    assert Dijkstra().calcular(g, "a", "b") is None


def test_origem_inexistente_devolve_none():
    assert Dijkstra().calcular(_grafo(("a", "b", 0.5)), "x", "b") is None
