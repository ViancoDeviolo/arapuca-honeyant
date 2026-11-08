"""TLS de verdade entre o app e o resumo-api: CA própria, IP no SAN, TLS 1.2+.

Roda no CI (sem a marca `integration`): só precisa do `openssl`, e pula se ele faltar.
"""

import shutil
import ssl
import subprocess  # nosec B404
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from honeyant.apps.certificados import emitir, gerar_ca, localizar_openssl
from honeyant.apps.resumo_ao_vivo import contexto_cliente
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.intel.acesso import ControleDeAcesso, gerar_hash
from honeyant.intel.adapters.servidor_resumo import contexto_servidor, criar_servidor

pytestmark = pytest.mark.skipif(localizar_openssl() is None, reason="precisa do openssl")

CHAVE = "chave-do-teste-de-tls-1234567890"


def _resumo():
    from pathlib import Path

    demo = Path(__file__).parents[2] / "docs" / "demo"
    return ResumoDeAmeaca.model_validate_json((demo / "resumo-congelado.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def ca(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("ca")
    gerar_ca(pasta)
    return pasta


def _servir(cert_dir, contexto=None):
    contexto = contexto or contexto_servidor(cert_dir / "servidor.crt", cert_dir / "servidor.key")
    srv = criar_servidor("127.0.0.1", 0, _resumo, ControleDeAcesso(gerar_hash(CHAVE)), contexto)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _buscar(porta, ca_crt):
    req = urllib.request.Request(f"https://127.0.0.1:{porta}/api/v1/resumo")  # noqa: S310
    req.add_header("Authorization", f"Bearer {CHAVE}")
    abridor = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=contexto_cliente(ca_crt))
    )
    with abridor.open(req, timeout=5) as r:
        return r.status


def test_ca_certa_e_ip_certo_conecta(ca, tmp_path):
    emitir("127.0.0.1", ca, tmp_path)
    srv = _servir(tmp_path)
    try:
        assert _buscar(srv.server_address[1], ca / "ca.crt") == 200
    finally:
        srv.shutdown()
        srv.server_close()


def test_certificado_de_outro_ip_recusa(ca, tmp_path):
    emitir("10.9.8.7", ca, tmp_path)
    srv = _servir(tmp_path)
    try:
        with pytest.raises(urllib.error.URLError) as erro:
            _buscar(srv.server_address[1], ca / "ca.crt")
        assert isinstance(erro.value.reason, ssl.SSLCertVerificationError)
    finally:
        srv.shutdown()
        srv.server_close()


def test_certificado_de_outra_ca_recusa(ca, tmp_path):
    outra = tmp_path / "outra-ca"
    gerar_ca(outra)
    emitir("127.0.0.1", outra, tmp_path / "srv")
    srv = _servir(tmp_path / "srv")
    try:
        with pytest.raises(urllib.error.URLError) as erro:
            _buscar(srv.server_address[1], ca / "ca.crt")
        assert isinstance(erro.value.reason, ssl.SSLCertVerificationError)
    finally:
        srv.shutdown()
        srv.server_close()


def test_tls_1_1_recusado(ca, tmp_path):
    emitir("127.0.0.1", ca, tmp_path)
    antigo = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        antigo.minimum_version = ssl.TLSVersion.TLSv1
        antigo.maximum_version = ssl.TLSVersion.TLSv1_1
    except (ValueError, ssl.SSLError):
        pytest.skip("o OpenSSL local nem oferece TLS 1.1")
    antigo.load_cert_chain(tmp_path / "servidor.crt", tmp_path / "servidor.key")
    srv = _servir(tmp_path, antigo)
    try:
        with pytest.raises((urllib.error.URLError, ssl.SSLError, ConnectionError)):
            _buscar(srv.server_address[1], ca / "ca.crt")
    finally:
        srv.shutdown()
        srv.server_close()


def test_contexto_do_cliente_exige_tls_1_2_e_confere_o_nome(ca):
    ctx = contexto_cliente(ca / "ca.crt")
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_certificado_tem_90_dias(ca, tmp_path):
    emitir("127.0.0.1", ca, tmp_path)
    saida = subprocess.run(  # noqa: S603  # nosec B603
        [localizar_openssl(), "x509", "-noout", "-enddate", "-in", str(tmp_path / "servidor.crt")],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    fim = datetime.strptime(saida.strip().split("=", 1)[1], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=UTC
    )
    dias = (fim - datetime.now(UTC)) / timedelta(days=1)
    assert 89 <= dias <= 90.01


def test_chave_da_ca_fica_so_no_ca_dir(ca, tmp_path):
    emitir("127.0.0.1", ca, tmp_path)
    assert (ca / "ca.key").is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["servidor.crt", "servidor.key"]


def test_sem_openssl_mensagem_clara(monkeypatch, tmp_path):
    from honeyant.apps import certificados

    monkeypatch.setattr(certificados, "localizar_openssl", lambda: None)
    with pytest.raises(certificados.ErroDeCertificado, match="openssl"):
        certificados.gerar_ca(tmp_path)


def test_openssl_encontrado():
    assert shutil.which("openssl") or localizar_openssl()


def test_conferir_resumo_com_chave_certa_e_errada(ca, tmp_path, capsys):
    """O comando do DEPLOY usa o mesmo cliente OpenSSL do app (o curl do Windows não
    aceita IP no certificado)."""
    from honeyant.apps import conferir_resumo

    emitir("127.0.0.1", ca, tmp_path)
    srv = _servir(tmp_path)
    url = f"https://127.0.0.1:{srv.server_address[1]}"
    try:
        assert conferir_resumo.main(["--url", url, "--ca", str(ca / "ca.crt")], chave=CHAVE) == 0
        assert "200" in capsys.readouterr().out
        assert conferir_resumo.main(["--url", url, "--ca", str(ca / "ca.crt")], chave="x") == 1
        assert "401" in capsys.readouterr().out
    finally:
        srv.shutdown()
        srv.server_close()


def test_cliente_silencioso_nao_trava_o_servidor(ca, tmp_path):
    """Revisão final, item 1: com o handshake dentro do accept(), uma conexão TCP que não
    manda nada travava o servidor inteiro. Agora o handshake é no thread de cada conexão."""
    import socket

    emitir("127.0.0.1", ca, tmp_path)
    srv = _servir(tmp_path)
    porta = srv.server_address[1]
    silencioso = socket.create_connection(("127.0.0.1", porta))
    try:
        assert _buscar(porta, ca / "ca.crt") == 200
    finally:
        silencioso.close()
        srv.shutdown()
        srv.server_close()


def test_cliente_ignora_o_proxy_do_sistema(ca, tmp_path, monkeypatch):
    """Na rede da faculdade, o proxy do sistema mudaria o IP visto pela EC2 (lista do
    Security Group). O cliente sempre conecta direto."""
    import ssl as _ssl

    from honeyant.apps.resumo_ao_vivo import ClienteResumo

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")  # proxy que não existe
    monkeypatch.setenv("NO_PROXY", "")
    emitir("127.0.0.1", ca, tmp_path)
    srv = _servir(tmp_path)
    try:
        cliente = ClienteResumo(
            f"https://127.0.0.1:{srv.server_address[1]}", CHAVE, contexto_cliente(ca / "ca.crt")
        )
        assert cliente.buscar().total_eventos >= 0
    finally:
        srv.shutdown()
        srv.server_close()
    assert _ssl


def test_conferir_recusa_url_sem_https(capsys):
    from honeyant.apps import conferir_resumo

    assert conferir_resumo.main(["--url", "http://127.0.0.1"], chave="nao-deve-sair") == 2
    assert "https://" in capsys.readouterr().out


def test_ca_pela_metade_nao_e_sobrescrita(tmp_path):
    """Segunda revisão, menor 7: só a ca.key (ou só o ca.crt) é um estado quebrado; gerar
    outra CA invalidaria todos os apps já distribuídos."""
    from honeyant.apps import certificados

    (tmp_path / "ca.key").write_text("chave antiga", encoding="utf-8")
    with pytest.raises(certificados.ErroDeCertificado, match="metade"):
        gerar_ca(tmp_path)
    assert (tmp_path / "ca.key").read_text(encoding="utf-8") == "chave antiga"
