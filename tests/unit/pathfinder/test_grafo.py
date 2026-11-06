"""Montagem do grafo de risco a partir das fixtures de docs/demo (o caminho da demo)."""

import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import montar_grafo

DEMO = Path(__file__).parents[3] / "docs" / "demo"


def _ler(nome: str):
    return json.loads((DEMO / nome).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def modelo():
    return ModeloDeRisco()


@pytest.fixture(scope="module")
def resumo():
    return ResumoDeAmeaca.model_validate(_ler("resumo-congelado.json"))


def _grafo(tipo, resumo, modelo):
    perfil = PerfilDaCasa.model_validate(_ler(f"perfil-{tipo}.json"))
    evid = combinar_evidencias(
        EvidenciaDeRede.model_validate(e) for e in _ler(f"evidencias-{tipo}.json")
    )
    return montar_grafo(perfil, evid, resumo, modelo)


def test_aresta_bloqueada_sai_do_grafo(resumo, modelo):
    assert "camera->broker" in _grafo("inseguro", resumo, modelo).chaves()
    assert "camera->broker" not in _grafo("seguro", resumo, modelo).chaves()


def test_aresta_sem_evidencia_assume_o_pior(resumo, modelo, agora):
    perfil = PerfilDaCasa.model_validate(_ler("perfil-inseguro.json"))
    sem_evidencia = montar_grafo(perfil, {}, resumo, modelo)
    com_evidencia = _grafo("seguro", resumo, modelo)
    assert sem_evidencia.risco("broker->fechadura") > com_evidencia.risco("broker->fechadura")


def test_demo_rota_pela_camera_antes_e_mais_cara_depois(resumo, modelo):
    """O teste da demonstração: a prova numérica da mitigação."""
    antes = Dijkstra().calcular(_grafo("inseguro", resumo, modelo), "internet", "fechadura")
    depois = Dijkstra().calcular(_grafo("seguro", resumo, modelo), "internet", "fechadura")
    assert antes.nos == ["internet", "camera", "broker", "fechadura"]
    assert depois is None or ("camera" not in depois.nos and depois.custo > antes.custo)
