"""As fixtures de docs/demo/ são o ponto de partida de pathfinder, painel e E2E.

Estes testes garantem que elas respeitam os contratos e são coerentes entre si.
"""

import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.eventos import Servico
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Snapshot

DEMO = Path(__file__).parents[3] / "docs" / "demo"
NAO_OBSERVADOS = {Servico.LAN, Servico.UPNP, Servico.TELNET}


def _json(nome: str):
    return json.loads((DEMO / nome).read_text(encoding="utf-8"))


def _perfil(tipo: str) -> PerfilDaCasa:
    return PerfilDaCasa.model_validate(_json(f"perfil-{tipo}.json"))


def _evidencias(tipo: str) -> list[EvidenciaDeRede]:
    return [EvidenciaDeRede.model_validate(e) for e in _json(f"evidencias-{tipo}.json")]


def test_resumo_congelado_valido_e_camera_usa_a_mais_tentada():
    r = ResumoDeAmeaca.model_validate(_json("resumo-congelado.json"))
    assert r.top_credenciais[0].tentativas == max(c.tentativas for c in r.top_credenciais)


@pytest.mark.parametrize("tipo", ["inseguro", "seguro"])
def test_perfil_tem_8_nos_e_fraqueza_fixa_so_onde_o_sensor_nao_ve(tipo):
    p = _perfil(tipo)
    assert len(p.nos) == 8 and p.perfil == tipo
    for a in p.arestas:
        assert (a.fraqueza_fixa is not None) == (a.servico in NAO_OBSERVADOS), a.chave


@pytest.mark.parametrize("tipo", ["inseguro", "seguro"])
def test_evidencias_cobrem_exatamente_as_arestas_observadas(tipo):
    p = _perfil(tipo)
    observadas = {a.chave for a in p.arestas if a.fraqueza_fixa is None}
    assert set(combinar_evidencias(_evidencias(tipo))) == observadas


def test_mitigacao_isola_a_camera():
    antes = combinar_evidencias(_evidencias("inseguro"))["camera->broker"]
    depois = combinar_evidencias(_evidencias("seguro"))["camera->broker"]
    assert antes.alcancavel is True and antes.credencial_vazada is True
    assert depois.alcancavel is False


def test_snapshots_de_exemplo_usam_arestas_do_perfil():
    chaves = {a.chave for a in _perfil("inseguro").arestas}
    linhas = (DEMO / "snapshots-exemplo.jsonl").read_text(encoding="utf-8").splitlines()
    snaps = [Snapshot.model_validate_json(linha) for linha in linhas]
    assert [s.iteracao for s in snaps] == list(range(len(snaps)))
    for s in snaps:
        assert set(s.feromonio) <= chaves
        for caminho in s.caminhos + ([s.melhor.nos] if s.melhor else []):
            assert caminho[0] == "internet" and caminho[-1] == "fechadura"
            pares = {f"{a}->{b}" for a, b in zip(caminho, caminho[1:], strict=False)}
            assert pares <= chaves
