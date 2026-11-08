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
    assert ler_chave(config, perguntar=lambda _: "chave-nova-123") == "chave-nova-123"


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


def test_chave_com_aspas_curvas_e_recusada_e_pergunta_de_novo(tmp_path, capsys):
    respostas = iter(["abc”", "abc-certa"])
    chave = ler_chave(tmp_path / "config.json", perguntar=lambda _: next(respostas))
    assert chave == "abc-certa"
    assert "aspas" in capsys.readouterr().out


def test_duas_chaves_invalidas_fica_sem_chave(tmp_path):
    assert ler_chave(tmp_path / "config.json", perguntar=lambda _: "com espaço") is None


def test_esquecer_chave_faz_perguntar_na_proxima(tmp_path):
    config = tmp_path / "config.json"
    ler_chave(config, perguntar=lambda _: "chave-velha-123")
    aplicativo.esquecer_chave(config)
    assert ler_chave(config, perguntar=lambda _: "chave-nova-123") == "chave-nova-123"


def test_chave_digitada_nao_aparece_na_tela():
    import getpass
    import inspect

    assert inspect.signature(ler_chave).parameters["perguntar"].default is getpass.getpass


def test_chave_salva_invalida_pergunta_de_novo(tmp_path):
    """Segunda revisão, menor 6: config.json editado à mão com caractere estranho."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"chave": "abc“def-ghi"}), encoding="utf-8")
    assert ler_chave(config, perguntar=lambda _: "chave-boa-123") == "chave-boa-123"


def test_confirma_quantos_caracteres_chegaram(tmp_path, capsys):
    """Segunda revisão, menor 10: o getpass não mostra nada; o app confirma o tamanho."""
    ler_chave(tmp_path / "config.json", perguntar=lambda _: "x" * 43)
    assert "43 caracteres" in capsys.readouterr().out


def test_appdata_sem_permissao_nao_derruba_o_app(tmp_path):
    """Terceira revisão: não conseguir salvar a chave não impede de usá-la nesta sessão."""
    bloqueio = tmp_path / "HoneyAnt"
    bloqueio.write_text("isto é um arquivo, não uma pasta", encoding="utf-8")
    assert (
        ler_chave(bloqueio / "config.json", perguntar=lambda _: "chave-da-sessao")
        == "chave-da-sessao"
    )


@pytest.mark.parametrize(
    "colado",
    [
        "Chave de acesso (entregue a cada pessoa por fora): abc-123-chave",
        "HONEYANT_RESUMO_CHAVE_HASH='scrypt$16384$8$1$abc$def'",
        "scrypt$16384$8$1$abc$def",
        "'abc-123-chave'",
    ],
)
def test_rotulo_hash_ou_aspas_sao_recusados_antes_de_ir_ao_servidor(tmp_path, capsys, colado):
    """Colar o rótulo ou o hash não vira chave salva (nem tentativa gasta no servidor)."""
    respostas = iter([colado, "abc-123-chave"])
    config = tmp_path / "config.json"
    assert ler_chave(config, perguntar=lambda _: next(respostas)) == "abc-123-chave"
    assert "Cole de novo só a chave" in capsys.readouterr().out
    assert json.loads(config.read_text(encoding="utf-8")) == {"chave": "abc-123-chave"}


def test_hash_salvo_no_config_nao_e_usado_como_chave(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"chave": "scrypt$16384$8$1$abc$def"}), encoding="utf-8")
    assert ler_chave(config, perguntar=lambda _: "chave-boa-123") == "chave-boa-123"
