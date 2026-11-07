"""Sensor: leitor de .pcap, CONNECT do MQTT, detector e o comando honeyant-sensor."""

import json
import struct
from datetime import UTC, datetime
from pathlib import Path

import pytest

from honeyant.apps import sensor as app_sensor
from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, Fonte, combinar_evidencias
from honeyant.sensor.adapters.pcap import ETHERNET, SLL2, FormatoNaoSuportado, LeitorPcap
from honeyant.sensor.detector import detectar
from honeyant.sensor.mqtt import ler_connect
from honeyant.sensor.ports import SegmentoTcp

RAIZ = Path(__file__).parents[3]
DEMO = RAIZ / "docs" / "demo"
CAPTURAS = RAIZ / "docs" / "capturas"
INSTANTE = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


# ---------- construtores de bytes (só dados de teste) ----------


def _str(s: bytes) -> bytes:
    return struct.pack(">H", len(s)) + s


def _varint(n: int) -> bytes:
    saida = bytearray()
    while True:
        b, n = n % 128, n // 128
        saida.append(b | (0x80 if n else 0))
        if not n:
            return bytes(saida)


def connect(
    id_: str, usuario: str | None = None, senha: str | None = None, versao: int = 4
) -> bytes:
    flags = (0x80 if usuario is not None else 0) | (0x40 if senha is not None else 0) | 0x02
    corpo = _str(b"MQTT") + bytes([versao, flags]) + struct.pack(">H", 60)
    if versao == 5:
        corpo += _varint(0)
    corpo += _str(id_.encode())
    if usuario is not None:
        corpo += _str(usuario.encode())
    if senha is not None:
        corpo += _str(senha.encode())
    return b"\x10" + _varint(len(corpo)) + corpo


def _tcp(sport: int, dport: int, dados: bytes) -> bytes:
    return struct.pack(">HHIIBBHHH", sport, dport, 1, 0, 5 << 4, 0x18, 502, 0, 0) + dados


def _ipv4(origem: str, destino: str, tcp: bytes) -> bytes:
    ip = bytes(map(int, origem.split("."))), bytes(map(int, destino.split(".")))
    return struct.pack(">BBHHHBBH", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0) + ip[0] + ip[1] + tcp


def _quadro(enlace: int, ip: bytes) -> bytes:
    if enlace == ETHERNET:
        return b"\x00" * 12 + b"\x08\x00" + ip
    return b"\x08\x00" + b"\x00" * 18 + ip  # SLL2: protocolo nos 2 primeiros bytes


def gravar_pcap(caminho: Path, pacotes: list[bytes], enlace: int = SLL2) -> Path:
    dados = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, enlace)
    for i, quadro in enumerate(pacotes):
        dados += struct.pack("<IIII", 1794081600 + i, 0, len(quadro), len(quadro)) + quadro
    caminho.write_bytes(dados)
    return caminho


def _pacote(dados: bytes, dport: int = 1883, enlace: int = SLL2) -> bytes:
    return _quadro(enlace, _ipv4("172.20.0.7", "172.20.0.2", _tcp(40000, dport, dados)))


@pytest.fixture(scope="module")
def perfil() -> PerfilDaCasa:
    return PerfilDaCasa.model_validate_json((DEMO / "perfil-inseguro.json").read_text("utf-8"))


class Fonte_:
    def __init__(self, segmentos):
        self._s = segmentos

    def segmentos(self):
        return iter(self._s)


def _seg(dados: bytes, dport: int = 1883) -> SegmentoTcp:
    return SegmentoTcp(INSTANTE, "10.0.0.2", 40000, "10.0.0.1", dport, dados)


# ---------- MQTT ----------


@pytest.mark.parametrize("versao", [4, 5])
def test_connect_com_usuario_e_senha(versao):
    c = ler_connect(connect("camera", "admin", "admin", versao))
    assert (c.versao, c.id_cliente, c.usuario, c.senha) == (versao, "camera", "admin", "admin")


def test_connect_sem_credencial():
    c = ler_connect(connect("lampada"))
    assert c.usuario is None and c.senha is None


@pytest.mark.parametrize(
    "lixo",
    [b"", b"\x10", b"\x30\x05abcde", b"\x10\xff\xff\xff\xff\x7f", connect("camera", "a", "b")[:-3],
     b"\x10\x08" + _str(b"HTTP") + b"\x04\x00\x00\x3c"],
)  # fmt: skip
def test_bytes_invalidos_nunca_quebram(lixo):
    assert ler_connect(lixo) is None


# ---------- pcap ----------


@pytest.mark.parametrize("enlace", [ETHERNET, SLL2])
def test_leitor_pcap_devolve_o_segmento_tcp(tmp_path, enlace):
    arq = gravar_pcap(tmp_path / "t.pcap", [_pacote(b"oi", enlace=enlace)], enlace)
    [s] = list(LeitorPcap(arq).segmentos())
    assert (s.origem, s.destino, s.porta_destino, s.dados) == (
        "172.20.0.7",
        "172.20.0.2",
        1883,
        b"oi",
    )
    assert s.instante.tzinfo is UTC


def test_pcap_truncado_le_o_que_der(tmp_path):
    arq = gravar_pcap(tmp_path / "t.pcap", [_pacote(b"um"), _pacote(b"dois")])
    arq.write_bytes(arq.read_bytes()[:-5])
    assert [s.dados for s in LeitorPcap(arq).segmentos()] == [b"um"]


def test_pcapng_e_recusado_com_dica(tmp_path):
    arq = tmp_path / "x.pcapng"
    arq.write_bytes(struct.pack("<I", 0x0A0D0D0A) + b"\x00" * 40)
    with pytest.raises(FormatoNaoSuportado, match="editcap"):
        list(LeitorPcap(arq).segmentos())


def test_arquivo_que_nao_e_pcap(tmp_path):
    arq = tmp_path / "x.pcap"
    arq.write_bytes(b"isto nao e um pcap de verdade....")
    with pytest.raises(FormatoNaoSuportado):
        list(LeitorPcap(arq).segmentos())


# ---------- detector ----------


def test_connect_em_claro_vira_texto_puro_e_credencial_vazada(perfil):
    fonte = Fonte_([_seg(connect("camera", "admin", "admin"))])
    [e] = detectar(fonte, perfil, {("admin", "admin")})
    assert (e.aresta, e.fonte, e.texto_puro, e.credencial_vazada) == (
        "camera->broker",
        Fonte.PASSIVO,
        True,
        True,
    )
    assert e.autenticacao_exigida is None and e.alcancavel is None  # passivo não infere isso


def test_senha_fora_do_top_da_isca_nao_e_vazada(perfil):
    [e] = detectar(Fonte_([_seg(connect("lampada", "lampada", "x"))]), perfil, {("admin", "admin")})
    assert e.credencial_vazada is False


def test_fechadura_usa_a_aresta_na_direcao_do_perfil(perfil):
    [e] = detectar(Fonte_([_seg(connect("fechadura-comando"))]), perfil)
    assert e.aresta == "broker->fechadura" and e.credencial_vazada is None


def test_ignora_tls_cliente_desconhecido_e_lixo(perfil):
    fonte = Fonte_([
        _seg(connect("camera", "admin", "admin"), dport=8883),
        _seg(connect("aspirador", "a", "b")),
        _seg(b"\x16\x03\x01\x00\x10"),
    ])  # fmt: skip
    assert detectar(fonte, perfil) == []


def test_uma_evidencia_por_aresta(perfil):
    fonte = Fonte_(
        [_seg(connect("camera", "u", "s")), _seg(connect("camera-comando", "admin", "admin"))]
    )
    [e] = detectar(fonte, perfil, {("admin", "admin")})
    assert e.credencial_vazada is True


# ---------- capturas reais (docs/capturas) ----------


def test_antes_pcap_bate_com_as_evidencias_da_demo(perfil):
    """O que o sensor identifica no antes.pcap concorda com a fixture usada pelo pathfinder."""
    detectadas = detectar(LeitorPcap(CAPTURAS / "antes.pcap"), perfil, {("admin", "admin")})
    fixture = combinar_evidencias(
        EvidenciaDeRede.model_validate(e)
        for e in json.loads((DEMO / "evidencias-inseguro.json").read_text("utf-8"))
    )
    assert {e.aresta for e in detectadas} >= {"camera->broker"}
    for e in detectadas:
        assert e.texto_puro is fixture[e.aresta].texto_puro is True
        assert e.credencial_vazada == fixture[e.aresta].credencial_vazada


def test_depois_pcap_nao_tem_texto_puro(perfil):
    assert detectar(LeitorPcap(CAPTURAS / "depois.pcap"), perfil, {("admin", "admin")}) == []


def test_comando_grava_o_json(tmp_path, capsys):
    saida = tmp_path / "ev.json"
    assert (
        app_sensor.main(
            [str(CAPTURAS / "antes.pcap"), "--saida", str(saida), "--demo-dir", str(DEMO)]
        )
        == 0
    )
    dados = json.loads(saida.read_text("utf-8"))
    camera = next(e for e in dados if e["aresta"] == "camera->broker")
    assert camera["texto_puro"] is True and camera["credencial_vazada"] is True
    assert "camera->broker: MQTT em texto puro e credencial vazada" in capsys.readouterr().err


def test_comando_com_arquivo_invalido_sai_com_erro(tmp_path, capsys):
    ruim = tmp_path / "x.pcap"
    ruim.write_bytes(b"nada")
    assert app_sensor.main([str(ruim), "--demo-dir", str(DEMO)]) == 1
    assert "erro:" in capsys.readouterr().err
