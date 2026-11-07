"""honeyant-app: painel só em 127.0.0.1, portas 8765–8774, chave no perfil do usuário."""

import json
import socket
from pathlib import Path

import pytest

from honeyant.apps import aplicativo
from honeyant.apps.aplicativo import PortasOcupadas, abrir_socket, ler_chave, recursos

RAIZ = Path(__file__).parents[3]


def _livre() -> int:
    """Uma porta inicial com as 10 seguintes livres (para não depender de 8765)."""
    for inicio in range(40000, 60000, 37):
        socks = []
        try:
            for p in range(inicio, inicio + 10):
                s = socket.socket()
                s.bind(("127.0.0.1", p))
                socks.append(s)
            return inicio
        except OSError:
            continue
        finally:
            for s in socks:
                s.close()
    pytest.skip("sem 10 portas seguidas livres")


def test_bind_so_em_127_0_0_1():
    sock = abrir_socket(_livre())
    try:
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        sock.close()


def test_porta_ocupada_usa_a_proxima():
    inicio = _livre()
    ocupada = socket.socket()
    ocupada.bind(("127.0.0.1", inicio))
    ocupada.listen()
    try:
        sock = abrir_socket(inicio)
        assert sock.getsockname()[1] == inicio + 1
        sock.close()
    finally:
        ocupada.close()


def test_todas_ocupadas_mensagem_clara():
    ocupadas = []
    try:
        for p in range(8765, 8775):
            s = socket.socket()
            try:
                s.bind(("127.0.0.1", p))
            except OSError:
                s.close()
                continue  # já ocupada por outro programa: também conta
            s.listen()
            ocupadas.append(s)
        with pytest.raises(PortasOcupadas) as erro:
            abrir_socket()
        assert str(erro.value) == (
            "As portas 8765 a 8774 estão ocupadas. Feche outro HoneyAnt aberto e tente de novo."
        )
    finally:
        for s in ocupadas:
            s.close()


def test_chave_colada_com_espacos_e_quebra_de_linha(tmp_path):
    config = tmp_path / "HoneyAnt" / "config.json"
    chave = ler_chave(config, perguntar=lambda _: "  abc123-chave \r\n")
    assert chave == "abc123-chave"
    assert json.loads(config.read_text("utf-8")) == {"chave": "abc123-chave"}
    # Na segunda vez, lê do arquivo e não pergunta.
    assert ler_chave(config, perguntar=lambda _: pytest.fail("não devia perguntar")) == chave


def test_config_corrompido_pergunta_de_novo(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"chave": ', encoding="utf-8")
    assert ler_chave(config, perguntar=lambda _: "nova") == "nova"


def test_enter_vazio_fica_sem_chave(tmp_path):
    config = tmp_path / "config.json"
    assert ler_chave(config, perguntar=lambda _: "   ") is None
    assert not config.exists()


def test_recursos_em_desenvolvimento_aponta_para_docs_demo():
    assert recursos() == RAIZ
    assert (recursos() / "docs" / "demo" / "perfil-inseguro.json").is_file()


def test_recursos_empacotado_usa_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(aplicativo.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert recursos() == tmp_path


def test_abre_o_navegador_sozinho_salvo_com_honeyant_sem_navegador():
    abertos = []
    aplicativo.abrir_navegador("http://127.0.0.1:8765/", env={}, abrir=abertos.append, espera_s=0)
    assert abertos == ["http://127.0.0.1:8765/"]
    abertos.clear()
    aplicativo.abrir_navegador(
        "http://127.0.0.1:8765/", env={"HONEYANT_SEM_NAVEGADOR": "1"}, abrir=abertos.append
    )
    assert abertos == []
