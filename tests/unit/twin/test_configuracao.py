"""Configuração do twin gerada a partir da planta: perfis, ACL, credenciais e compose."""

import json
from itertools import count
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.core.credenciais import credenciais_conhecidas
from honeyant.twin import configuracao as cfg
from honeyant.twin.planta import planejar_dispositivos

RAIZ = Path(__file__).parents[3]
DEMO = RAIZ / "docs" / "demo"
INSEGURO, SEGURO = TipoDePerfil.INSEGURO, TipoDePerfil.SEGURO


def _perfil(tipo: TipoDePerfil) -> PerfilDaCasa:
    return PerfilDaCasa.model_validate_json((DEMO / f"perfil-{tipo.value}.json").read_text("utf-8"))


def _senhas():
    contador = count(1)
    return lambda: f"forte-{next(contador)}"


@pytest.fixture
def dispositivos():
    return planejar_dispositivos(_perfil(INSEGURO))


def test_camera_usa_a_credencial_padrao_de_fabrica_conhecida():
    camera = cfg.credencial_da_camera()
    assert camera == cfg.Credencial("admin", "admin")
    assert (camera.usuario, camera.senha) in credenciais_conhecidas()


def test_inseguro_camera_com_a_vazada_e_os_outros_previsiveis(dispositivos):
    c = cfg.credenciais(INSEGURO, dispositivos, cfg.Credencial("admin", "admin"), _senhas())
    assert c["camera"] == cfg.Credencial("admin", "admin")
    assert c["lampada"] == cfg.Credencial("lampada", "lampada")
    assert set(c) == {d.id for d in dispositivos} | {cfg.USUARIO_MONITOR}


def test_seguro_senha_aleatoria_por_usuario(dispositivos):
    c = cfg.credenciais(SEGURO, dispositivos, cfg.Credencial("admin", "admin"), _senhas())
    senhas = [x.senha for x in c.values()]
    assert len(set(senhas)) == len(senhas)
    assert all(s.startswith("forte-") for s in senhas)
    assert c["camera"].usuario == "camera"


def test_acl_cada_dispositivo_so_nos_proprios_topicos(dispositivos):
    usuarios = cfg.credenciais(SEGURO, dispositivos, cfg.Credencial("a", "b"), _senhas())
    texto = cfg.acl(dispositivos, usuarios)
    bloco = texto.split("user camera\n")[1].split("\n\n")[0]
    assert bloco == "topic write casa/camera/estado\ntopic read casa/camera/comando"
    assert "#" not in texto.replace("# Gerado", "").replace(
        "casa/#", ""
    )  # só o monitor usa curinga
    assert "user monitor\ntopic read casa/#" in texto


def test_conf_inseguro_texto_puro_e_anonimo():
    conf = cfg.mosquitto_conf(INSEGURO)
    assert "listener 1883" in conf and "allow_anonymous true" in conf
    assert "certfile" not in conf and "password_file" not in conf


def test_conf_seguro_tls_senha_e_acl():
    conf = cfg.mosquitto_conf(SEGURO)
    assert "listener 8883" in conf and "allow_anonymous false" in conf
    for chave in ("cafile", "certfile", "keyfile", "password_file", "acl_file"):
        assert chave in conf
    assert "1883" not in conf


def test_compose_seguro_isola_a_camera_e_usa_tls(dispositivos):
    servicos = cfg.compose_dispositivos(SEGURO, dispositivos)["services"]
    assert servicos["camera"]["networks"] == [cfg.REDE_CAMERA]
    assert all(s["networks"] == [cfg.REDE_CASA] for i, s in servicos.items() if i != "camera")
    assert all(s["environment"]["MQTT_PORTA"] == "8883" for s in servicos.values())
    assert all(s["environment"]["MQTT_CAFILE"] == "/certs/ca.crt" for s in servicos.values())


def test_compose_inseguro_todos_na_mesma_rede_sem_tls(dispositivos):
    servicos = cfg.compose_dispositivos(INSEGURO, dispositivos)["services"]
    assert set(servicos) == {d.id for d in dispositivos}
    assert all(s["networks"] == [cfg.REDE_CASA] for s in servicos.values())
    assert all("MQTT_CAFILE" not in s["environment"] for s in servicos.values())
    assert servicos["camera"]["environment"]["TOPICO_ESTADO"] == "casa/camera/estado"


def test_compose_nao_carrega_senha_so_referencia_ao_env(dispositivos):
    usuarios = cfg.credenciais(SEGURO, dispositivos, cfg.Credencial("a", "b"), _senhas())
    texto = json.dumps(cfg.compose_dispositivos(SEGURO, dispositivos))
    assert not any(c.senha in texto for c in usuarios.values())
    assert "${SENHA_CAMERA}" in texto
    env = cfg.env(SEGURO, usuarios)
    assert "PERFIL=seguro" in env and f"SENHA_CAMERA={usuarios['camera'].senha}" in env


def test_imagem_do_compose_base_e_a_mesma_fixada():
    base = (RAIZ / "infra" / "twin" / "compose.yml").read_text("utf-8")
    assert cfg.IMAGEM_MOSQUITTO in base
