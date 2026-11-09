"""E2E do painel local: fixtures → fuzzy → ACO/Dijkstra → API e SSE (spec do painel, 3.2–3.4)."""

import json
import math
import shutil
from pathlib import Path

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient

from honeyant.apps.local import ConfigLocal, FonteDoResumoLocal, montar
from honeyant.core.rota import Snapshot
from honeyant.painel.app import Encaixe

pytestmark = pytest.mark.e2e

DEMO = Path(__file__).parents[2] / "docs" / "demo"
LOCAL = "http://127.0.0.1"


def _cliente(demo_dir: Path = DEMO, **kwargs) -> TestClient:
    config = ConfigLocal(demo_dir=demo_dir, host="127.0.0.1", porta=0)
    app = montar(config, intervalo_base=0, intervalo_minimo=0, **kwargs)
    return TestClient(app, base_url=LOCAL)


def stream(perfil: str, semente: int = 42) -> list[Snapshot]:
    r = _cliente().get("/api/v1/formigueiro/stream", params={"perfil": perfil, "semente": semente})
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


def test_e2e_stream_por_perfil():
    antes, depois = stream("inseguro")[-1], stream("seguro")[-1]
    assert "camera" not in depois.melhor.nos
    assert depois.melhor.custo > antes.melhor.custo


def test_e2e_mesma_semente_mesmos_snapshots():
    assert stream("inseguro", 42) == stream("inseguro", 42)


def test_e2e_rotas_e_razao():
    j = _cliente().get("/api/v1/rotas").json()
    ins, seg = j["inseguro"], j["seguro"]
    assert ins["rota"]["nos"] == ["internet", "camera", "broker", "fechadura"]
    assert seg["rota"]["nos"] == ["internet", "roteador", "broker", "fechadura"]
    assert seg["bloqueadas"] == ["camera->broker"]
    assert set(ins["riscos"]) == {"internet->camera", "camera->broker", "broker->fechadura"}
    assert ins["riscos_por_no"]["camera"] == max(
        ins["riscos"]["internet->camera"], ins["riscos"]["camera->broker"]
    )
    razao = ins["rota"]["plausibilidade"] / seg["rota"]["plausibilidade"]
    esperado = math.exp(seg["rota"]["custo"] - ins["rota"]["custo"])
    assert razao == pytest.approx(esperado, rel=1e-9)


def test_casa_dos_dois_perfis():
    c = _cliente()
    assert c.get("/api/v1/casa", params={"perfil": "seguro"}).json()["perfil"] == "seguro"


def test_resumo_cai_no_exemplo_sem_arquivo_real(tmp_path):
    # Cópia das fixtures sem nenhum resumo-real-*.json (o docs/demo de verdade pode ter um).
    shutil.copy(DEMO / "resumo-congelado.json", tmp_path / "resumo-congelado.json")
    r = FonteDoResumoLocal(tmp_path).resumo()
    assert r.origem == "exemplo"


def test_resumo_real_mais_recente_vence(tmp_path):
    base = json.loads((DEMO / "resumo-congelado.json").read_text("utf-8"))
    for data in ["2026-11-06", "2026-11-07", "2026-10-30"]:
        (tmp_path / f"resumo-real-{data}.json").write_text(
            json.dumps({**base, "gerado_em": f"{data}T12:00:00Z"}), encoding="utf-8"
        )
    r = FonteDoResumoLocal(tmp_path).resumo()
    assert r.origem == "real"
    assert r.resumo.gerado_em.date().isoformat() == "2026-11-07"


def test_replay_sem_arquivo(tmp_path):
    for nome in DEMO.iterdir():
        if not nome.name.startswith("replay-"):
            shutil.copy(nome, tmp_path / nome.name)
    c = _cliente(tmp_path)
    assert c.get("/api/v1/replay").json() == {"inseguro": False, "seguro": False}
    r = c.get("/api/v1/formigueiro/stream", params={"modo": "replay"})
    assert r.status_code == 404


def test_config_padrao_so_escuta_localhost():
    c = ConfigLocal.de_ambiente({})
    assert (c.host, c.porta) == ("127.0.0.1", 8000)
    assert c.demo_dir == Path("docs/demo")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.0.10"])  # noqa: S104
def test_config_recusa_host_fora_do_loopback(host):
    with pytest.raises(ValueError, match="não há modo nuvem"):
        ConfigLocal.de_ambiente({"HONEYANT_HOST": host})


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_config_aceita_loopback(host):
    assert ConfigLocal.de_ambiente({"HONEYANT_HOST": host}).host == host


def test_montar_repassa_o_encaixe_do_login():
    def recusa() -> None:
        raise HTTPException(401)

    c = _cliente(encaixe=Encaixe(protecao_api=[Depends(recusa)]))
    assert c.get("/api/v1/casa").status_code == 401


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_montar_aceita_os_hosts_de_loopback(host):
    config = ConfigLocal(demo_dir=DEMO, host="127.0.0.1", porta=0)
    assert TestClient(montar(config), base_url=f"http://{host}").get("/").status_code == 200
