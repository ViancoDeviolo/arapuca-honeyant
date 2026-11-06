import math
from uuid import uuid4

import pytest
from pydantic import ValidationError

from honeyant.core.rota import Algoritmo, Rota, Snapshot

NOS = ["internet", "camera", "broker", "fechadura"]


def _rota(**extra) -> Rota:
    padrao = {"nos": NOS, "custo": 1.5, "plausibilidade": math.exp(-1.5), "algoritmo": "aco"}
    return Rota(**(padrao | extra))


def test_rota_valida():
    r = _rota()
    assert r.algoritmo is Algoritmo.ACO
    assert r.arestas == ["internet->camera", "camera->broker", "broker->fechadura"]


def test_plausibilidade_coerente_com_custo():
    with pytest.raises(ValidationError, match="plausibilidade"):
        _rota(plausibilidade=0.9)


def test_custo_positivo_e_finito():
    for custo in (-1.0, math.inf, math.nan):
        with pytest.raises(ValidationError):
            _rota(custo=custo, plausibilidade=0.5)


def test_rota_nao_repete_no_e_tem_ao_menos_uma_aresta():
    with pytest.raises(ValidationError):
        _rota(nos=["internet", "camera", "internet", "fechadura"])
    with pytest.raises(ValidationError):
        _rota(nos=["internet"])


def _snapshot(**extra) -> Snapshot:
    padrao = {
        "execucao_id": uuid4(),
        "semente": 42,
        "iteracao": 0,
        "feromonio": {"internet->camera": 0.1, "camera->broker": 0.1},
        "caminhos": [NOS],
        "melhor": None,
    }
    return Snapshot(**(padrao | extra))


def test_snapshot_valido_e_ida_e_volta():
    s = _snapshot(melhor=_rota())
    assert Snapshot.model_validate_json(s.model_dump_json()) == s


def test_snapshot_limita_caminhos():
    with pytest.raises(ValidationError):
        _snapshot(caminhos=[NOS] * 21)


def test_snapshot_feromonio_com_chave_de_aresta_e_valor_nao_negativo():
    with pytest.raises(ValidationError):
        _snapshot(feromonio={"camera": 0.1})
    with pytest.raises(ValidationError):
        _snapshot(feromonio={"camera->broker": -0.1})


def test_snapshot_iteracao_nao_negativa():
    with pytest.raises(ValidationError):
        _snapshot(iteracao=-1)
