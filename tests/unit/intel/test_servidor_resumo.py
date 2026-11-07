"""resumo-api: só GET /api/v1/resumo, chave Bearer, cache de 15 s, 503 sem banco."""

import json
import re
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from honeyant.apps import servir_resumo
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.intel.acesso import ControleDeAcesso, gerar_hash
from honeyant.intel.adapters.servidor_resumo import criar_servidor

DEMO = Path(__file__).parents[3] / "docs" / "demo"
CHAVE = "chave-de-teste-do-resumo-api-1234567890"
HASH = gerar_hash(CHAVE)
QUALQUER_IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def _resumo() -> ResumoDeAmeaca:
    return ResumoDeAmeaca.model_validate_json((DEMO / "resumo-congelado.json").read_text("utf-8"))


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class Fonte:
    def __init__(self) -> None:
        self.chamadas = 0
        self.falhar = False

    def __call__(self) -> ResumoDeAmeaca:
        self.chamadas += 1
        if self.falhar:
            raise sqlite3.OperationalError("database is locked")
        return _resumo()


@pytest.fixture
def servidor():
    """Sobe o servidor sem TLS numa porta livre; devolve (url, fonte, relogio)."""
    fonte, relogio = Fonte(), Relogio()
    acesso = ControleDeAcesso(HASH, relogio=relogio)
    srv = criar_servidor("127.0.0.1", 0, fonte, acesso, None, relogio=relogio,
                         timeout_conexao_s=0.5)  # fmt: skip
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", fonte, relogio
    srv.shutdown()
    srv.server_close()


def _get(url, chave=CHAVE, metodo="GET"):
    req = urllib.request.Request(url, method=metodo)  # noqa: S310  # http local do teste
    if chave is not None:
        req.add_header("Authorization", f"Bearer {chave}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_resumo_com_chave_certa_200_sem_ipv4(servidor):
    url, _, _ = servidor
    status, corpo, cab = _get(f"{url}/api/v1/resumo")
    assert status == 200
    assert cab["Content-Type"].startswith("application/json")
    ResumoDeAmeaca.model_validate_json(corpo)
    assert not QUALQUER_IPV4.search(corpo.decode())


def test_sem_chave_401_e_bloqueio_429(servidor):
    url, _, _ = servidor
    for _ in range(5):
        assert _get(f"{url}/api/v1/resumo", chave="errada")[0] == 401
    assert _get(f"{url}/api/v1/resumo")[0] == 429


@pytest.mark.parametrize(
    ("rota", "metodo"),
    [("/", "GET"), ("/api/v1/casa", "GET"), ("/api/v1/resumo", "POST"), ("/api/v1/resumo", "PUT")],
)
def test_outra_rota_e_outro_metodo_404_vazio(servidor, rota, metodo):
    url, _, _ = servidor
    status, corpo, cab = _get(f"{url}{rota}", metodo=metodo)
    assert status == 404
    assert corpo == b""
    assert cab["Server"] == "honeyant"


def test_cache_de_15_s(servidor):
    url, fonte, relogio = servidor
    for _ in range(3):
        assert _get(f"{url}/api/v1/resumo")[0] == 200
    assert fonte.chamadas == 1
    relogio.t += 16
    _get(f"{url}/api/v1/resumo")
    assert fonte.chamadas == 2


def test_banco_indisponivel_503(servidor):
    url, fonte, _ = servidor
    fonte.falhar = True
    status, corpo, _ = _get(f"{url}/api/v1/resumo")
    assert (status, corpo) == (503, b"")
    fonte.falhar = False
    assert _get(f"{url}/api/v1/resumo")[0] == 200


def test_conexao_lenta_e_fechada(servidor):
    url, _, _ = servidor
    porta = int(url.rsplit(":", 1)[1])
    with socket.create_connection(("127.0.0.1", porta), timeout=5) as s:
        inicio = time.monotonic()
        assert s.recv(1024) == b""  # o servidor fecha sem resposta
        assert time.monotonic() - inicio < 3


def test_log_nunca_tem_a_chave(servidor, capsys):
    url, _, _ = servidor
    _get(f"{url}/api/v1/resumo")
    _get(f"{url}/api/v1/resumo", chave="outra-chave-errada")
    saida = capsys.readouterr()
    texto = saida.out + saida.err
    assert '"status": 200' in texto
    assert CHAVE not in texto and "outra-chave-errada" not in texto
    assert "Authorization" not in texto and "Bearer" not in texto


def test_main_sem_hash_recusa_subir(monkeypatch, capsys):
    monkeypatch.delenv("HONEYANT_RESUMO_CHAVE_HASH", raising=False)
    with pytest.raises(SystemExit) as saida:
        servir_resumo.main()
    assert saida.value.code not in (0, None)
    assert "honeyant-chave-app" in capsys.readouterr().err


def test_main_com_hash_invalido_recusa_subir(monkeypatch, capsys):
    monkeypatch.setenv("HONEYANT_RESUMO_CHAVE_HASH", "nao-e-hash")
    with pytest.raises(SystemExit) as saida:
        servir_resumo.main()
    assert saida.value.code not in (0, None)


def test_fonte_do_banco_agrega_sem_ip(tmp_path, fabrica_evento):
    from honeyant.arapuca.adapters.sqlite import RepositorioSqlite

    banco = tmp_path / "isca.db"
    RepositorioSqlite(banco).salvar(fabrica_evento(usuario="MGLNDD_203.0.113.7_23"))
    from datetime import UTC, datetime

    resumo = servir_resumo.fonte_do_banco(banco)()
    assert resumo.gerado_em <= datetime.now(UTC)
    assert not QUALQUER_IPV4.search(resumo.model_dump_json())
    json.loads(resumo.model_dump_json())


def test_linha_corrompida_no_banco_da_503(servidor):
    """Evento que não valida (ValidationError é ValueError) não derruba a conexão."""
    url, fonte, _ = servidor

    def corrompida():
        raise ValueError("linha corrompida no banco")

    fonte_original = fonte.__call__
    fonte.falhar = False
    type(fonte).__call__ = lambda self: corrompida()
    try:
        status, corpo, _ = _get(f"{url}/api/v1/resumo")
        assert (status, corpo) == (503, b"")
    finally:
        type(fonte).__call__ = Fonte.__call__
    assert fonte_original


def test_erro_de_conexao_vira_uma_linha_json(capsys):
    """Segunda revisão, menor 3: handshake quebrado ou HTTP puro na porta TLS não despeja
    traceback no log."""
    from honeyant.intel.adapters.servidor_resumo import criar_servidor

    srv = criar_servidor("127.0.0.1", 0, Fonte(), ControleDeAcesso(HASH), None)
    try:
        try:
            raise ConnectionResetError("cliente sumiu")
        except ConnectionResetError:
            srv.handle_error(None, ("203.0.113.7", 50000))
    finally:
        srv.server_close()
    err = capsys.readouterr().err
    assert json.loads(err.strip().splitlines()[-1]) == {
        "erro": "conexao",
        "tipo": "ConnectionResetError",
    }
    assert "Traceback" not in err and "203.0.113.7" not in err
