"""API do painel (spec, seções 3.2 a 3.4): casa, resumo, rotas, replay e stream."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Snapshot
from honeyant.painel.app import criar_app
from honeyant.painel.modelos import AnaliseDeRota, ResumoComOrigem
from honeyant.painel.streams import RegistroDeStreams

DEMO = Path(__file__).parents[3] / "docs" / "demo"
CSP = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)
STREAM = "/api/v1/formigueiro/stream"


def _casas() -> dict[TipoDePerfil, PerfilDaCasa]:
    return {
        t: PerfilDaCasa.model_validate_json((DEMO / f"perfil-{t.value}.json").read_text("utf-8"))
        for t in TipoDePerfil
    }


def _snapshots() -> list[Snapshot]:
    linhas = (DEMO / "snapshots-exemplo.jsonl").read_text("utf-8").splitlines()
    return [Snapshot.model_validate_json(linha) for linha in linhas[:3]]


ANALISE = AnaliseDeRota(
    rota=None,
    riscos={"internet->camera": 0.9},
    riscos_por_no={"camera": 0.9},
    bloqueadas=["camera->broker"],
)


class FonteFalsa:
    def __init__(self, snapshots=None, replays=None):
        self.lista = _snapshots() if snapshots is None else snapshots
        self.replays = replays or {}
        self.pedidos: list[tuple] = []

    def snapshots(self, perfil, semente):
        self.pedidos.append((perfil, semente))
        return self.lista

    def replay(self, perfil):
        return self.replays.get(perfil)

    def analise(self, perfil):
        return ANALISE


class ResumoFalso:
    def resumo(self):
        dados = json.loads((DEMO / "resumo-congelado.json").read_text("utf-8"))
        return ResumoComOrigem(origem="exemplo", resumo=ResumoDeAmeaca.model_validate(dados))


async def _sem_espera(_segundos: float) -> None:
    return None


def _cliente(fonte=None, **extra) -> TestClient:
    extra.setdefault("dormir", _sem_espera)
    app = criar_app(_casas(), fonte or FonteFalsa(), ResumoFalso(), **extra)
    return TestClient(app, base_url="http://127.0.0.1")


def eventos_sse(texto: str) -> list[tuple[str, str]]:
    saida = []
    for bloco in texto.strip().split("\n\n"):
        campos = dict(linha.split(": ", 1) for linha in bloco.splitlines())
        saida.append((campos["event"], campos["data"]))
    return saida


def test_casa_por_perfil():
    c = _cliente()
    assert c.get("/api/v1/casa", params={"perfil": "seguro"}).json()["perfil"] == "seguro"
    assert c.get("/api/v1/casa").json()["perfil"] == "inseguro"


def test_perfil_antigo_sumiu():
    assert _cliente().get("/api/v1/perfil").status_code == 404


def test_casa_com_perfil_invalido_da_422():
    assert _cliente().get("/api/v1/casa", params={"perfil": "xyz"}).status_code == 422


def test_resumo_traz_a_origem():
    j = _cliente().get("/api/v1/resumo").json()
    assert j["origem"] == "exemplo"
    assert j["resumo"]["total_eventos"] >= 0


def test_rotas_dos_dois_perfis():
    j = _cliente().get("/api/v1/rotas").json()
    assert set(j) == {"inseguro", "seguro"}
    assert j["seguro"]["bloqueadas"] == ["camera->broker"]
    assert j["inseguro"]["riscos_por_no"] == {"camera": 0.9}


def test_replay_disponivel():
    fonte = FonteFalsa(replays={TipoDePerfil.INSEGURO: _snapshots()})
    assert _cliente(fonte).get("/api/v1/replay").json() == {"inseguro": True, "seguro": False}


def test_stream_replay_usa_os_snapshots_gravados():
    gravados = _snapshots()[:2]
    fonte = FonteFalsa(replays={TipoDePerfil.SEGURO: gravados})
    r = _cliente(fonte).get(STREAM, params={"perfil": "seguro", "modo": "replay"})
    recebidos = [Snapshot.model_validate_json(d) for e, d in eventos_sse(r.text) if e == "snapshot"]
    assert recebidos == gravados
    assert fonte.pedidos == []


def test_stream_replay_sem_arquivo_da_404():
    r = _cliente().get(STREAM, params={"modo": "replay"})
    assert r.status_code == 404
    assert r.json() == {"detail": "replay indisponível para este perfil"}


@pytest.mark.parametrize(
    "q",
    [
        "perfil=xyz",
        "modo=xyz",
        "velocidade=10",
        "velocidade=0.1",
        "velocidade=nan",
        "velocidade=inf",
        "velocidade=abc",
        "semente=-1",
        f"semente={2**31}",
        "semente=1.5",
    ],
)
def test_limite_invalido_da_422_sem_rodar_a_fonte(q):
    fonte = FonteFalsa()
    r = _cliente(fonte).get(f"{STREAM}?{q}")
    assert r.status_code == 422
    assert fonte.pedidos == []


def test_parametros_do_aco_vindos_do_cliente_sao_ignorados():
    fonte = FonteFalsa()
    r = _cliente(fonte).get(f"{STREAM}?perfil=seguro&semente=7&iteracoes=1000&formigas=999")
    assert r.status_code == 200
    assert fonte.pedidos == [(TipoDePerfil.SEGURO, 7)]


def test_stream_termina_com_fim():
    fonte = FonteFalsa()
    eventos = eventos_sse(_cliente(fonte).get(STREAM).text)
    assert [e for e, _ in eventos] == ["snapshot"] * 3 + ["fim"]
    assert [Snapshot.model_validate_json(d) for e, d in eventos if e == "snapshot"] == fonte.lista


def test_snapshot_sem_rota_vai_como_null():
    sem_rota = [s.model_copy(update={"melhor": None}) for s in _snapshots()]
    r = _cliente(FonteFalsa(sem_rota)).get(STREAM)
    assert all(json.loads(d)["melhor"] is None for e, d in eventos_sse(r.text) if e == "snapshot")


@pytest.mark.parametrize(("velocidade", "esperas"), [(4, [0.15, 0.15]), (1, [0.6, 0.6])])
def test_intervalo_respeita_o_minimo(velocidade, esperas):
    pedidas: list[float] = []

    async def dormir(segundos: float) -> None:
        pedidas.append(segundos)

    _cliente(dormir=dormir).get(STREAM, params={"velocidade": velocidade})
    assert pedidas == pytest.approx(esperas)


def test_o_stream_mais_novo_vence():
    registro = RegistroDeStreams()
    primeiro = registro.abrir("a")
    segundo = registro.abrir("a")
    outro = registro.abrir("b")
    assert primeiro.is_set()
    assert not segundo.is_set()
    assert not outro.is_set()
    registro.fechar("a", primeiro)  # fechar o antigo não derruba o novo
    terceiro = registro.abrir("a")
    assert segundo.is_set() and not terceiro.is_set()


def test_stream_antigo_para_quando_outro_abre():
    """Um stream novo do mesmo cliente, aberto no meio do antigo, faz o antigo emitir `fim`."""
    registro = RegistroDeStreams()
    app_cliente: dict = {}

    async def dormir(_s: float) -> None:
        # No primeiro intervalo do stream antigo, o mesmo cliente abre outro.
        if not app_cliente.get("aberto"):
            app_cliente["aberto"] = True
            registro.abrir("testclient")  # o IP que o TestClient informa
        await asyncio.sleep(0)

    c = _cliente(dormir=dormir, registro=registro)
    eventos = eventos_sse(c.get(STREAM).text)
    assert [e for e, _ in eventos] == ["snapshot", "fim"]


@pytest.mark.parametrize("caminho", ["/", "/api/v1/casa", "/api/v1/rotas"])
def test_csp_em_toda_resposta(caminho):
    r = _cliente().get(caminho)
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == CSP
    assert r.headers["x-content-type-options"] == "nosniff"
