import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, Fonte
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.pathfinder.aco import ACO, ParametrosACO
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.prever import ColetorDeSnapshots, prever_rota

DEMO = Path(__file__).parents[3] / "docs" / "demo"
PELA_CAMERA = ["internet", "camera", "broker", "fechadura"]
PELO_ROTEADOR = ["internet", "roteador", "broker", "fechadura"]


def _json(nome):
    return json.loads((DEMO / nome).read_text(encoding="utf-8"))


def perfil(tipo):
    return PerfilDaCasa.model_validate(_json(f"perfil-{tipo}.json"))


def evid(tipo):
    return [EvidenciaDeRede.model_validate(e) for e in _json(f"evidencias-{tipo}.json")]


def resumo():
    return ResumoDeAmeaca.model_validate(_json("resumo-congelado.json"))


def test_inseguro_passa_pela_camera():
    rota = prever_rota(perfil("inseguro"), evid("inseguro"), resumo(), ACO())
    assert rota.nos == PELA_CAMERA
    assert rota.custo == pytest.approx(1.422, abs=1e-3)


def test_mitigar_muda_a_rota_e_encarece():
    antes = prever_rota(perfil("inseguro"), evid("inseguro"), resumo(), ACO())
    depois = prever_rota(perfil("seguro"), evid("seguro"), resumo(), ACO())
    assert depois.nos == PELO_ROTEADOR
    assert depois.custo > antes.custo


def test_coletor_recebe_um_snapshot_por_iteracao():
    coletor = ColetorDeSnapshots()
    prever_rota(
        perfil("inseguro"),
        evid("inseguro"),
        resumo(),
        ACO(ParametrosACO(iteracoes=7), observadores=[coletor]),
    )
    assert [s.iteracao for s in coletor.snapshots] == list(range(7))


def test_sem_caminho_ate_a_fechadura_devolve_none():
    p = perfil("inseguro")
    depois = datetime(2030, 1, 1, tzinfo=UTC)  # mais recente que qualquer fixture
    bloqueios = [
        EvidenciaDeRede(aresta=a.chave, observado_em=depois, fonte=Fonte.ATIVO, alcancavel=False)
        for a in p.arestas
        if a.destino == "broker"
    ]
    # Arestas com fraqueza_fixa (lan) não têm evidência; as *->broker são todas mqtt.
    assert bloqueios
    bloqueadas = evid("inseguro") + bloqueios
    assert prever_rota(p, bloqueadas, resumo(), ACO()) is None
    assert prever_rota(p, bloqueadas, resumo(), Dijkstra()) is None
