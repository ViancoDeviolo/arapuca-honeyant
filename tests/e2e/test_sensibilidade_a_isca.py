"""Quanto a isca muda a rota nesta casa: contrafactual sobre as fixtures (ADR 0005).

Medido na auditoria de 09/11: a fraqueza e a exposição dominam o fuzzy. A frequência de
ataques vinda da isca muda a *plausibilidade* da rota, não a rota. Este teste trava esse
comportamento. Se ele falhar depois de mexer no fuzzy ou nos perfis, atualize a seção
"Sensibilidade medida (09/11)" do ADR 0005 junto com os números daqui.
"""

import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import montar_grafo

pytestmark = pytest.mark.e2e

DEMO = Path(__file__).parents[2] / "docs" / "demo"
ROTA_INSEGURA = ["internet", "camera", "broker", "fechadura"]
ROTA_SEGURA = ["internet", "roteador", "broker", "fechadura"]
PLAUSIBILIDADE_BASE = 0.2412  # telnet domina (ou zero ataques): a frequência não pesa
PLAUSIBILIDADE_MQTT_100 = 0.3726
PLAUSIBILIDADE_MQTT_50 = 0.2921
RISCO_INTERNET_CAMERA = 0.795  # fraqueza 8, exposição 9: saturado
CUSTO_SEGURO = 4.8559

MODELO = ModeloDeRisco()


def _json(nome: str):
    return json.loads((DEMO / nome).read_text("utf-8"))


def _resumo_com(por_servico: dict[str, int]) -> ResumoDeAmeaca:
    base = _json("resumo-congelado.json")
    return ResumoDeAmeaca.model_validate(
        {**base, "total_eventos": sum(por_servico.values()), "por_servico": por_servico}
    )


RESUMOS = {
    "zero-ataques": lambda: _resumo_com({}),
    "congelado": lambda: ResumoDeAmeaca.model_validate(_json("resumo-congelado.json")),
    "real-2026-11-07": lambda: ResumoDeAmeaca.model_validate(_json("resumo-real-2026-11-07.json")),
    "mqtt-100": lambda: _resumo_com({"mqtt": 100}),
    "telnet-mqtt-50-50": lambda: _resumo_com({"telnet": 50, "mqtt": 50}),
}


def _grafo(perfil: str, resumo: ResumoDeAmeaca):
    casa = PerfilDaCasa.model_validate(_json(f"perfil-{perfil}.json"))
    evidencias = combinar_evidencias(
        EvidenciaDeRede.model_validate(e) for e in _json(f"evidencias-{perfil}.json")
    )
    return casa, montar_grafo(casa, evidencias, resumo, MODELO)


def _rota(perfil: str, resumo: ResumoDeAmeaca):
    casa, grafo = _grafo(perfil, resumo)
    return Dijkstra().calcular(grafo, casa.origem, casa.alvo)


@pytest.mark.parametrize("caso", ["zero-ataques", "congelado", "real-2026-11-07"])
def test_sem_mqtt_dominante_a_isca_nao_muda_rota_nem_plausibilidade(caso):
    rota = _rota("inseguro", RESUMOS[caso]())
    assert rota.nos == ROTA_INSEGURA
    assert rota.plausibilidade == pytest.approx(PLAUSIBILIDADE_BASE, rel=1e-3)


@pytest.mark.parametrize(
    ("caso", "plausibilidade"),
    [("mqtt-100", PLAUSIBILIDADE_MQTT_100), ("telnet-mqtt-50-50", PLAUSIBILIDADE_MQTT_50)],
)
def test_mqtt_dominante_aumenta_a_plausibilidade_sem_mudar_a_rota(caso, plausibilidade):
    rota = _rota("inseguro", RESUMOS[caso]())
    assert rota.nos == ROTA_INSEGURA
    assert rota.plausibilidade == pytest.approx(plausibilidade, rel=1e-3)
    assert rota.plausibilidade > PLAUSIBILIDADE_BASE


@pytest.mark.parametrize("freq", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_risco_de_internet_camera_satura_em_qualquer_frequencia(freq):
    # A mesma conta que o montar_grafo faz para a aresta (fraqueza_fixa 8, exposição 9)...
    assert MODELO.risco(freq, 8, 9) == pytest.approx(RISCO_INTERNET_CAMERA, rel=1e-3)


@pytest.mark.parametrize("caso", list(RESUMOS))
def test_risco_de_internet_camera_no_grafo_nao_depende_do_resumo(caso):
    # ...e o que de fato chega ao grafo, com cada um dos resumos.
    _, grafo = _grafo("inseguro", RESUMOS[caso]())
    assert grafo.risco("internet->camera") == pytest.approx(RISCO_INTERNET_CAMERA, rel=1e-3)


@pytest.mark.parametrize("caso", list(RESUMOS))
def test_perfil_seguro_mantem_a_rota_pelo_roteador(caso):
    rota = _rota("seguro", RESUMOS[caso]())
    assert rota.nos == ROTA_SEGURA
    assert rota.custo == pytest.approx(CUSTO_SEGURO, rel=1e-3)
