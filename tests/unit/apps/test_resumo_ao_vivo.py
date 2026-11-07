"""Fonte do resumo no app: ao vivo → cache (offline) → embutido, recuo e parada no 401."""

import json
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from honeyant.apps.resumo_ao_vivo import (
    AVISO_CHAVE_INVALIDA,
    ChaveInvalida,
    ClienteResumo,
    FalhaDeRede,
    FonteDoResumoAoVivo,
    RespostaInvalida,
)
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.painel.modelos import ResumoComOrigem

DEMO = Path(__file__).parents[3] / "docs" / "demo"
AGORA = datetime(2026, 11, 8, 15, 4, tzinfo=UTC)


def _resumo(total: int = 7) -> ResumoDeAmeaca:
    dados = json.loads((DEMO / "resumo-congelado.json").read_text("utf-8"))
    dados["total_eventos"] = total
    dados["por_servico"] = {"telnet": total}
    return ResumoDeAmeaca.model_validate(dados)


class Embutido:
    def resumo(self) -> ResumoComOrigem:
        return ResumoComOrigem(origem="real", resumo=_resumo(1))


class Relogio:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


class ClienteFalso:
    def __init__(self, *respostas) -> None:
        self.respostas = list(respostas)
        self.chamadas = 0

    def buscar(self) -> ResumoDeAmeaca:
        self.chamadas += 1
        r = self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def relogio():
    return Relogio()


def _fonte(cliente, tmp_path, relogio, **extra):
    """Síncrona nos testes de lógica: a busca acontece dentro do resumo()."""
    return FonteDoResumoAoVivo(
        cliente,
        tmp_path / "ultimo-resumo.json",
        Embutido(),
        relogio=relogio,
        agora=lambda: AGORA,
        em_segundo_plano=extra.pop("em_segundo_plano", False),
        **extra,
    )


def test_sucesso_e_ao_vivo_e_grava_cache(tmp_path, relogio):
    r = _fonte(ClienteFalso(_resumo(42)), tmp_path, relogio).resumo()
    assert r.origem == "ao_vivo" and r.resumo.total_eventos == 42
    assert r.atualizado_em == AGORA
    cache = json.loads((tmp_path / "ultimo-resumo.json").read_text("utf-8"))
    assert cache["resumo"]["total_eventos"] == 42


def test_falha_de_rede_usa_cache_offline(tmp_path, relogio):
    _fonte(ClienteFalso(_resumo(42)), tmp_path, relogio).resumo()  # grava o cache
    r = _fonte(ClienteFalso(FalhaDeRede("sem rede")), tmp_path, relogio).resumo()
    assert r.origem == "offline"
    assert r.resumo.total_eventos == 42
    assert r.atualizado_em == AGORA


def test_sem_cache_usa_embutido(tmp_path, relogio):
    r = _fonte(ClienteFalso(FalhaDeRede("sem rede")), tmp_path, relogio).resumo()
    assert r.origem == "real" and r.resumo.total_eventos == 1


def test_401_para_de_consultar(tmp_path, relogio):
    cliente = ClienteFalso(ChaveInvalida())
    fonte = _fonte(cliente, tmp_path, relogio)
    r = fonte.resumo()
    for _ in range(5):
        relogio.t += 400
        r = fonte.resumo()
    assert cliente.chamadas == 1
    assert r.aviso == AVISO_CHAVE_INVALIDA == "chave de acesso inválida"
    assert r.origem in {"offline", "real"}


def test_recuo_exponencial_com_teto(tmp_path, relogio):
    cliente = ClienteFalso(FalhaDeRede("sem rede"))
    fonte = _fonte(cliente, tmp_path, relogio)
    esperas = []
    for _ in range(7):
        fonte.resumo()
        esperas.append(fonte.espera_s)
        relogio.t += fonte.espera_s - 0.1
        chamadas = cliente.chamadas
        fonte.resumo()  # antes da hora: não consulta
        assert cliente.chamadas == chamadas
        relogio.t += 0.1
    assert esperas == [15, 30, 60, 120, 240, 300, 300]
    cliente.respostas = [_resumo(5)]
    fonte.resumo()
    assert fonte.espera_s == 15


def test_entre_consultas_repete_o_ultimo_ao_vivo(tmp_path, relogio):
    cliente = ClienteFalso(_resumo(42))
    fonte = _fonte(cliente, tmp_path, relogio)
    fonte.resumo()
    relogio.t += 5
    r = fonte.resumo()
    assert cliente.chamadas == 1 and r.origem == "ao_vivo"


def test_resposta_invalida_descartada(tmp_path, relogio):
    r = _fonte(ClienteFalso(RespostaInvalida("lixo")), tmp_path, relogio).resumo()
    assert r.origem == "real"
    assert not (tmp_path / "ultimo-resumo.json").exists()


def test_cache_corrompido_e_ignorado(tmp_path, relogio):
    (tmp_path / "ultimo-resumo.json").write_text('{"resumo": {"total_eve', encoding="utf-8")
    r = _fonte(ClienteFalso(FalhaDeRede("x")), tmp_path, relogio).resumo()
    assert r.origem == "real"


def test_cache_gravado_de_forma_atomica(tmp_path, relogio, monkeypatch):
    import os

    trocas = []
    original = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (trocas.append((a, b)), original(a, b)))
    _fonte(ClienteFalso(_resumo(42)), tmp_path, relogio).resumo()
    assert len(trocas) == 1 and Path(trocas[0][1]) == tmp_path / "ultimo-resumo.json"
    assert not list(tmp_path.glob("*.tmp"))


def test_sem_chave_fica_offline_sem_rede(tmp_path, relogio):
    r = _fonte(None, tmp_path, relogio).resumo()
    assert r.origem == "real" and r.aviso is None


def test_servidor_que_nao_responde_nao_trava(tmp_path, relogio):
    import ssl

    escuta = socket.socket()
    escuta.bind(("127.0.0.1", 0))
    escuta.listen(1)  # aceita a conexão e nunca responde
    porta = escuta.getsockname()[1]
    try:
        cliente = ClienteResumo(
            f"https://127.0.0.1:{porta}", "chave", ssl.create_default_context(), timeout_s=1
        )
        fonte = _fonte(cliente, tmp_path, relogio)
        inicio = time.monotonic()
        r = fonte.resumo()
        assert time.monotonic() - inicio < 6
        assert r.origem == "real"
    finally:
        escuta.close()


def test_cliente_traduz_401_e_json_invalido(tmp_path):
    """Servidor HTTP local (sem TLS) só para conferir a tradução das respostas."""
    import http.server
    import ssl

    respostas = iter([(401, b""), (200, b'{"nao": "e um resumo"}')])

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, corpo = next(respostas)
            self.send_response(status)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        cliente = ClienteResumo(url, "chave", ssl.create_default_context(), timeout_s=2)
        with pytest.raises(ChaveInvalida):
            cliente.buscar()
        with pytest.raises(RespostaInvalida):
            cliente.buscar()
    finally:
        srv.shutdown()
        srv.server_close()


def test_montar_usa_a_fonte_de_resumo_externa_e_a_rota_nao_muda():
    """O app troca só a fonte do resumo (cartões e formigas); a rota segue o embutido."""
    from fastapi.testclient import TestClient

    from honeyant.apps.local import ConfigLocal, montar

    class AoVivoFalso:
        def resumo(self):
            return ResumoComOrigem(origem="ao_vivo", resumo=_resumo(999), atualizado_em=AGORA)

    base = "http://127.0.0.1"
    padrao = TestClient(montar(ConfigLocal(DEMO, "127.0.0.1", 0)), base_url=base)
    vivo = TestClient(
        montar(ConfigLocal(DEMO, "127.0.0.1", 0), fonte_resumo=AoVivoFalso()), base_url=base
    )
    r = vivo.get("/api/v1/resumo").json()
    assert r["origem"] == "ao_vivo" and r["resumo"]["total_eventos"] == 999
    assert vivo.get("/api/v1/rotas").json() == padrao.get("/api/v1/rotas").json()


# ---------- revisão final: página nunca espera a EC2, erros inesperados, 401, console ----------


class ClienteLento:
    def __init__(self, segundos):
        self.segundos = segundos

    def buscar(self):
        time.sleep(self.segundos)
        return _resumo(77)


def test_em_segundo_plano_a_pagina_nao_espera_a_ec2(tmp_path):
    fonte = FonteDoResumoAoVivo(
        ClienteLento(1.5), tmp_path / "c.json", Embutido(), em_segundo_plano=True
    )
    inicio = time.monotonic()
    r = fonte.resumo()
    assert time.monotonic() - inicio < 0.5
    assert r.origem == "real"  # na hora: o embutido
    for _ in range(40):
        time.sleep(0.1)
        if fonte.resumo().origem == "ao_vivo":
            break
    assert fonte.resumo().resumo.total_eventos == 77


class ClienteQueExplode:
    def buscar(self):
        raise UnicodeEncodeError("latin-1", "x", 0, 1, "aspas curvas na chave")


def test_erro_inesperado_vira_falha_de_rede_e_nao_500(tmp_path, relogio):
    fonte = _fonte(ClienteQueExplode(), tmp_path, relogio)
    r = fonte.resumo()
    assert r.origem == "real"
    assert fonte.espera_s == 15  # recuo agendado como uma falha de rede


def test_cliente_converte_qualquer_erro_em_falha_de_rede():
    import ssl

    cliente = ClienteResumo("https://127.0.0.1:1", "chave“", ssl.create_default_context(), 1)
    with pytest.raises(FalhaDeRede):
        cliente.buscar()


def test_401_chama_ao_recusar_uma_vez(tmp_path, relogio):
    recusas = []
    fonte = _fonte(
        ClienteFalso(ChaveInvalida()), tmp_path, relogio, ao_recusar=lambda: recusas.append(1)
    )
    for _ in range(3):
        fonte.resumo()
        relogio.t += 400
    assert recusas == [1]


def test_console_mostra_as_transicoes_sem_repetir(tmp_path, relogio):
    mensagens = []
    cliente = ClienteFalso(_resumo(1))
    fonte = _fonte(cliente, tmp_path, relogio, avisar=mensagens.append)
    fonte.resumo()
    relogio.t += 16
    fonte.resumo()  # continua ao vivo: sem mensagem nova
    cliente.respostas = [FalhaDeRede("IP bloqueado por 15 min (muitas chaves erradas)")]
    relogio.t += 16
    fonte.resumo()
    cliente.respostas = [ChaveInvalida()]
    relogio.t += 400
    fonte.resumo()
    assert mensagens[0].startswith("Ao vivo")
    assert "IP bloqueado por 15 min" in mensagens[1] and "offline" in mensagens[1].lower()
    assert "chave de acesso inválida" in mensagens[2].lower()
    assert len(mensagens) == 3
