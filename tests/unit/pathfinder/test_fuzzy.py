import itertools
import math

import pytest

from honeyant.pathfinder.fuzzy import RISCO_MAX, RISCO_MIN, ModeloDeRisco, custo_da_aresta


@pytest.fixture(scope="module")
def modelo() -> ModeloDeRisco:
    return ModeloDeRisco()


def test_risco_fica_entre_0_e_1(modelo):
    for f, w, e in itertools.product([0, 0.5, 1], [0, 5, 10], [0, 5, 10]):
        assert 0 <= modelo.risco(f, w, e) <= 1


def test_extremos_ordenados(modelo):
    baixo = modelo.risco(frequencia=0, fraqueza=0, exposicao=0)
    alto = modelo.risco(frequencia=1, fraqueza=10, exposicao=10)
    assert baixo < 0.3 and alto > 0.7


def test_fraqueza_alta_e_exposicao_alta_e_critico(modelo):
    """R4: mesmo sem ataques observados, fraqueza alta + exposição alta = crítico."""
    assert modelo.risco(frequencia=0, fraqueza=10, exposicao=10) > 0.7


def test_rejeita_entrada_fora_da_faixa(modelo):
    for args in [(-0.1, 5, 5), (1.1, 5, 5), (0.5, -1, 5), (0.5, 5, 11), (math.nan, 5, 5)]:
        with pytest.raises(ValueError):
            modelo.risco(*args)


def test_monotonicidade_na_grade_11x11x11(modelo):
    """Spec, seção 8: aumentar uma entrada nunca pode reduzir o risco."""
    passos = range(11)
    grade = {
        (i, j, k): modelo.risco(i / 10, j, k) for i, j, k in itertools.product(passos, repeat=3)
    }
    violacoes = []
    for (i, j, k), r in grade.items():
        for vizinho in [(i + 1, j, k), (i, j + 1, k), (i, j, k + 1)]:
            if vizinho in grade and grade[vizinho] < r - 1e-9:
                violacoes.append(((i, j, k), vizinho, r, grade[vizinho]))
    assert violacoes == []


def test_custo_e_menos_log_do_risco_limitado():
    assert custo_da_aresta(0.5) == pytest.approx(-math.log(0.5))
    assert custo_da_aresta(0.0) == pytest.approx(-math.log(RISCO_MIN))
    assert custo_da_aresta(1.0) == pytest.approx(-math.log(RISCO_MAX))
    assert custo_da_aresta(1.0) > 0
