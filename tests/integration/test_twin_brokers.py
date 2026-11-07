"""Os dois brokers de verdade (Docker): o inseguro aceita qualquer um; o seguro não.

Fora do CI padrão (`-m "not integration"`). Rodar com o Docker Desktop aberto:

    uv run pytest -m integration tests/integration/test_twin_brokers.py -v

Cada teste roda um cliente `mosquitto_pub`/`mosquitto_sub` num container na rede da casa.
"""

import shutil
import subprocess  # nosec B404
from pathlib import Path

import pytest

from honeyant.apps.twin import ControleDoTwin, executar_docker
from honeyant.core.casa import TipoDePerfil
from honeyant.twin.configuracao import IMAGEM_MOSQUITTO

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("docker") is None, reason="precisa do Docker"),
]
REDE = "honeyant-twin_casa"


def _cliente(script: str, certs: Path | None = None) -> subprocess.CompletedProcess:
    args = ["docker", "run", "--rm", "--network", REDE, "--entrypoint", "sh"]
    if certs:
        args += ["-v", f"{certs.resolve()}:/certs:ro"]
    return subprocess.run(  # noqa: S603  # nosec B603
        [*args, IMAGEM_MOSQUITTO, "-c", script], capture_output=True, text=True, timeout=60
    )


def _env(twin: ControleDoTwin, tipo: TipoDePerfil) -> dict[str, str]:
    linhas = (twin.pasta(tipo) / ".env").read_text("utf-8").splitlines()
    return dict(
        linha.split("=", 1) for linha in linhas if "=" in linha and not linha.startswith("#")
    )


@pytest.fixture(scope="module")
def twin():
    t = ControleDoTwin(docker=executar_docker)
    t.preparar()
    yield t
    t.descer()


@pytest.fixture
def inseguro(twin):
    twin.descer()
    twin.subir(TipoDePerfil.INSEGURO)
    return twin


@pytest.fixture
def seguro(twin):
    twin.descer()
    twin.subir(TipoDePerfil.SEGURO)
    return twin


def test_inseguro_cliente_sem_senha_publica_na_1883(inseguro):
    r = _cliente("mosquitto_pub -h broker -p 1883 -t casa/lampada/comando -m ligar")
    assert r.returncode == 0, r.stderr


def test_seguro_cliente_sem_senha_e_recusado(seguro):
    certs = seguro.pasta(TipoDePerfil.SEGURO) / "mosquitto" / "certs"
    r = _cliente("mosquitto_pub -h broker -p 8883 --cafile /certs/ca.crt -t casa/x -m oi", certs)
    assert r.returncode != 0
    assert "not authorised" in (r.stderr + r.stdout).lower()


def test_seguro_texto_puro_na_1883_nao_existe(seguro):
    r = _cliente("mosquitto_pub -h broker -p 1883 -t casa/x -m oi")
    assert r.returncode != 0


def test_seguro_com_tls_e_credencial_certa_publica(seguro):
    env = _env(seguro, TipoDePerfil.SEGURO)
    certs = seguro.pasta(TipoDePerfil.SEGURO) / "mosquitto" / "certs"
    r = _cliente(
        f"mosquitto_pub -h broker -p 8883 --cafile /certs/ca.crt "
        f"-u {env['USUARIO_LAMPADA']} -P {env['SENHA_LAMPADA']} "
        "-t casa/lampada/estado -m ok",
        certs,
    )
    assert r.returncode == 0, r.stderr


def test_seguro_camera_nao_publica_no_topico_de_outro_dispositivo(seguro):
    """O monitor escuta casa/lampada/estado: chega o da lâmpada, nunca o da câmera."""
    env = _env(seguro, TipoDePerfil.SEGURO)
    certs = seguro.pasta(TipoDePerfil.SEGURO) / "mosquitto" / "certs"
    tls = "-h broker -p 8883 --cafile /certs/ca.crt"
    script = (
        f"mosquitto_sub {tls} -u {env['USUARIO_MONITOR']} -P {env['SENHA_MONITOR']} "
        "-t casa/lampada/estado -W 6 > /tmp/recebido & sleep 2; "
        f"mosquitto_pub {tls} -u {env['USUARIO_CAMERA']} -P {env['SENHA_CAMERA']} "
        "-t casa/lampada/estado -m INTRUSO_DA_CAMERA; "
        f"mosquitto_pub {tls} -u {env['USUARIO_LAMPADA']} -P {env['SENHA_LAMPADA']} "
        "-t casa/lampada/estado -m LEGITIMO_DA_LAMPADA; "
        "wait; cat /tmp/recebido"
    )
    r = _cliente(script, certs)
    assert "LEGITIMO_DA_LAMPADA" in r.stdout, r.stderr  # o monitor funciona
    assert "INTRUSO_DA_CAMERA" not in r.stdout  # a ACL descartou a câmera
