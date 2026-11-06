"""E2E mínimo do esqueleto (spec, seção 17, 06/11 tarde): fixtures → fuzzy → ACO → SSE."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeyant.apps.local import ConfigLocal, montar
from honeyant.core.casa import TipoDePerfil
from honeyant.core.rota import Snapshot

pytestmark = pytest.mark.e2e

DEMO = Path(__file__).parents[2] / "docs" / "demo"


def stream(perfil: str, semente: int = 42) -> list[Snapshot]:
    config = ConfigLocal(perfil=TipoDePerfil(perfil), demo_dir=DEMO, host="127.0.0.1", porta=0)
    cliente = TestClient(montar(config, intervalo_base=0, intervalo_minimo=0))
    r = cliente.get("/api/v1/formigueiro/stream", params={"semente": semente})
    assert r.status_code == 200
    snaps = []
    for bloco in r.text.strip().split("\n\n"):
        evento, dados = (linha.split(": ", 1)[1] for linha in bloco.splitlines())
        if evento == "snapshot":
            snaps.append(Snapshot.model_validate_json(dados))
    return snaps


def test_e2e_inseguro_rota_pela_camera():
    s = stream("inseguro")[-1]
    assert s.iteracao == 49
    assert s.melhor.nos == ["internet", "camera", "broker", "fechadura"]


def test_e2e_mitigar_muda_rota_e_custo_sobe():
    antes, depois = stream("inseguro")[-1], stream("seguro")[-1]
    assert "camera" not in depois.melhor.nos
    assert depois.melhor.custo > antes.melhor.custo


def test_e2e_mesma_semente_mesmos_snapshots():
    assert stream("inseguro", 42) == stream("inseguro", 42)


def test_config_padrao_so_escuta_localhost():
    c = ConfigLocal.de_ambiente({})
    assert (c.host, c.porta, c.perfil) == ("127.0.0.1", 8000, TipoDePerfil.INSEGURO)
    assert c.demo_dir == Path("docs/demo")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.0.10"])  # noqa: S104
def test_config_recusa_host_fora_do_localhost_enquanto_nao_ha_login(host):
    with pytest.raises(ValueError, match="127.0.0.1"):
        ConfigLocal.de_ambiente({"HONEYANT_HOST": host})


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_config_aceita_loopback(host):
    assert ConfigLocal.de_ambiente({"HONEYANT_HOST": host}).host == host
