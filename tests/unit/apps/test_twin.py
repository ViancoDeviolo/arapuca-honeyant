"""`honeyant-twin`, `honeyant-mitigar` e `honeyant-capturar` com um docker falso."""

import json
import shutil
from itertools import count
from pathlib import Path

import pytest

from honeyant.apps import capturar, mitigar
from honeyant.apps.twin import ControleDoTwin, ErroDoTwin
from honeyant.core.casa import TipoDePerfil

DEMO = Path(__file__).parents[3] / "docs" / "demo"
COMPOSE = Path(__file__).parents[3] / "infra" / "twin" / "compose.yml"


class DockerFalso:
    def __init__(self) -> None:
        self.chamadas: list[list[str]] = []

    def __call__(self, argumentos):
        self.chamadas.append(list(argumentos))
        return ""

    def compose(self) -> list[list[str]]:
        return [c for c in self.chamadas if c[0] == "compose"]


@pytest.fixture
def twin(tmp_path):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo)
    dir_twin = tmp_path / "twin"
    dir_twin.mkdir()
    shutil.copy(COMPOSE, dir_twin / "compose.yml")
    contador = count(1)
    return ControleDoTwin(dir_twin, demo, DockerFalso(), lambda: f"Forte{next(contador):04d}")


def test_preparar_gera_os_dois_perfis(twin):
    twin.preparar()
    inseguro, seguro = twin.pasta(TipoDePerfil.INSEGURO), twin.pasta(TipoDePerfil.SEGURO)
    assert "allow_anonymous true" in (inseguro / "mosquitto" / "mosquitto.conf").read_text()
    assert "SENHA_CAMERA=admin" in (inseguro / ".env").read_text()
    assert (seguro / "mosquitto" / "acl").is_file()
    assert (seguro / "mosquitto" / "certs").is_dir()
    assert "SENHA_CAMERA=Forte" in (seguro / ".env").read_text()
    servicos = json.loads((seguro / "dispositivos.json").read_text())["services"]
    assert servicos["camera"]["networks"] == ["camera_isolada"]


def test_preparar_chama_hash_de_senha_e_gera_certificados(twin):
    twin.preparar()
    chamadas = [" ".join(c) for c in twin.docker.chamadas]
    assert any("mosquitto_passwd" in c and "-U /w/passwd" in c for c in chamadas)
    assert any("openssl" in c and "rm -f broker.csr ext.cnf ca.srl ca.key" in c for c in chamadas)


def test_env_e_senhas_nunca_entram_no_container_do_broker(twin):
    twin.preparar()
    assert not (twin.pasta(TipoDePerfil.SEGURO) / "mosquitto" / ".env").exists()
    assert "/mosquitto:/mosquitto/config:ro" in COMPOSE.read_text("utf-8")


def test_subir_sem_preparar_avisa(twin):
    with pytest.raises(ErroDoTwin, match="honeyant-twin preparar"):
        twin.subir(TipoDePerfil.INSEGURO)


def test_subir_usa_o_env_e_os_dispositivos_do_perfil_e_marca_ativo(twin):
    twin.preparar()
    twin.subir(TipoDePerfil.SEGURO)
    comando = twin.docker.compose()[-1]
    assert str(twin.pasta(TipoDePerfil.SEGURO) / ".env") in comando
    assert str(twin.pasta(TipoDePerfil.SEGURO) / "dispositivos.json") in comando
    assert comando[-3:] == ["up", "-d", "--force-recreate"]
    assert twin.ativo() is TipoDePerfil.SEGURO


def test_mitigar_e_desfazer_trocam_de_perfil(twin, capsys):
    twin.preparar()
    twin.subir(TipoDePerfil.INSEGURO)
    assert mitigar.main([], twin=twin) == 0
    assert twin.ativo() is TipoDePerfil.SEGURO
    assert "TLS na 8883" in capsys.readouterr().out
    downs = [c for c in twin.docker.compose() if "down" in c]
    assert downs and str(twin.pasta(TipoDePerfil.INSEGURO) / ".env") in downs[-1]

    assert mitigar.main(["--desfazer"], twin=twin) == 0
    assert twin.ativo() is TipoDePerfil.INSEGURO


def test_mitigar_sem_preparar_falha_com_mensagem(twin, capsys):
    assert mitigar.main([], twin=twin) == 1
    assert "honeyant-twin preparar" in capsys.readouterr().err


def test_capturar_liga_o_tcpdump_antes_dos_dispositivos(twin, tmp_path):
    twin.preparar()
    bruto = twin.dir / "capturas" / "inseguro.pcap"

    def parar(tipo, servicos):
        bruto.parent.mkdir(exist_ok=True)
        bruto.write_bytes(b"pcap de teste")

    twin.parar = parar
    final = capturar.capturar(twin, TipoDePerfil.INSEGURO, tmp_path / "out", 0, lambda s: None)
    assert final.name == "antes.pcap" and final.read_bytes() == b"pcap de teste"
    ups = [c for c in twin.docker.compose() if "up" in c]
    assert ups[0][-2:] == ["broker", "captura"]  # só broker + tcpdump primeiro
    assert ups[1][-1] == "--force-recreate"  # depois a casa inteira


def test_capturar_sem_pcap_falha(twin, tmp_path):
    twin.preparar()
    twin.parar = lambda tipo, servicos: None
    with pytest.raises(ErroDoTwin, match="não gravou nada"):
        capturar.capturar(twin, TipoDePerfil.SEGURO, tmp_path, 0, lambda s: None)
