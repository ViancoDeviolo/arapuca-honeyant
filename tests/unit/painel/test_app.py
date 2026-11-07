import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.rota import Snapshot
from honeyant.painel.app import criar_app

DEMO = Path(__file__).parents[3] / "docs" / "demo"
CSP = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)
STREAM = "/api/v1/formigueiro/stream"


def _perfil() -> PerfilDaCasa:
    return PerfilDaCasa.model_validate_json((DEMO / "perfil-inseguro.json").read_text("utf-8"))


def _snapshots() -> list[Snapshot]:
    linhas = (DEMO / "snapshots-exemplo.jsonl").read_text("utf-8").splitlines()
    return [Snapshot.model_validate_json(linha) for linha in linhas[:3]]


class FonteFalsa:
    def __init__(self, snapshots=None):
        self.lista = _snapshots() if snapshots is None else snapshots
        self.sementes: list[int] = []

    def snapshots(self, semente: int):
        self.sementes.append(semente)
        return self.lista


async def _sem_espera(_segundos: float) -> None:
    return None


def _cliente(fonte, **extra) -> TestClient:
    extra.setdefault("dormir", _sem_espera)
    return TestClient(criar_app(_perfil(), fonte, **extra), base_url="http://127.0.0.1")


def eventos_sse(texto: str) -> list[tuple[str, str]]:
    """Separa um corpo text/event-stream em pares (evento, dados)."""
    saida = []
    for bloco in texto.strip().split("\n\n"):
        campos = dict(linha.split(": ", 1) for linha in bloco.splitlines())
        saida.append((campos["event"], campos["data"]))
    return saida


def test_perfil_em_json():
    r = _cliente(FonteFalsa()).get("/api/v1/perfil")
    assert r.status_code == 200
    assert r.json()["perfil"] == "inseguro" and len(r.json()["nos"]) == 8


def test_stream_entrega_snapshots_validos_e_fim():
    fonte = FonteFalsa()
    r = _cliente(fonte).get(STREAM)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    eventos = eventos_sse(r.text)
    assert [e for e, _ in eventos] == ["snapshot"] * 3 + ["fim"]
    recebidos = [Snapshot.model_validate_json(d) for e, d in eventos if e == "snapshot"]
    assert recebidos == fonte.lista


def test_semente_chega_na_fonte():
    fonte = FonteFalsa()
    _cliente(fonte).get(STREAM, params={"semente": 7})
    assert fonte.sementes == [7]


@pytest.mark.parametrize(
    "q", ["velocidade=10", "velocidade=0.1", "velocidade=abc", "semente=-1", "modo=xyz"]
)
def test_query_invalida_da_422_sem_rodar_a_fonte(q):
    fonte = FonteFalsa()
    r = _cliente(fonte).get(f"{STREAM}?{q}")
    assert r.status_code == 422
    assert fonte.sementes == []


def test_snapshot_sem_rota_vai_como_null():
    sem_rota = [s.model_copy(update={"melhor": None}) for s in _snapshots()]
    r = _cliente(FonteFalsa(sem_rota)).get(STREAM)
    dados = [json.loads(d) for e, d in eventos_sse(r.text) if e == "snapshot"]
    assert all(d["melhor"] is None for d in dados)


@pytest.mark.parametrize(("velocidade", "esperas"), [(4, [0.15, 0.15]), (1, [0.6, 0.6])])
def test_intervalo_respeita_o_minimo(velocidade, esperas):
    pedidas: list[float] = []

    async def dormir(segundos: float) -> None:
        pedidas.append(segundos)

    _cliente(FonteFalsa(), dormir=dormir).get(STREAM, params={"velocidade": velocidade})
    assert pedidas == pytest.approx(esperas)


@pytest.mark.parametrize("caminho", ["/", "/api/v1/perfil"])
def test_csp_em_toda_resposta(caminho):
    r = _cliente(FonteFalsa()).get(caminho)
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == CSP
    assert r.headers["x-content-type-options"] == "nosniff"
