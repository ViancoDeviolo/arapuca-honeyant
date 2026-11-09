import struct

from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.mqtt import ServicoMqtt


def s(txt: str) -> bytes:
    b = txt.encode()
    return struct.pack("!H", len(b)) + b


def pacote(tipo: int, corpo: bytes) -> bytes:
    return bytes([tipo, len(corpo)]) + corpo


def connect_311(usuario="camera", senha="123456") -> bytes:
    corpo = s("MQTT") + b"\x04" + b"\xc2" + b"\x00\x3c" + s("cli1") + s(usuario) + s(senha)
    return pacote(0x10, corpo)


def publish(topico: str, payload: bytes = b"on") -> bytes:
    return pacote(0x30, s(topico) + payload)


def subscribe(filtro: str) -> bytes:
    return pacote(0x82, b"\x00\x01" + s(filtro) + b"\x00")


class Saida:
    def __init__(self):
        self.dados = bytearray()

    async def __call__(self, b):
        self.dados.extend(b)


async def test_captura_credenciais_e_publish(leitor_com):
    saida = Saida()
    dados = connect_311() + publish("casa/fechadura/cmd") + b"\xe0\x00"
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(dados)), saida)
    assert (cap.usuario, cap.senha) == ("camera", "123456")
    assert cap.comandos == ["PUBLISH casa/fechadura/cmd"]
    assert saida.dados.startswith(b"\x20\x02\x00\x00")


async def test_subscribe_e_ping_recebem_resposta(leitor_com):
    saida = Saida()
    dados = connect_311() + subscribe("#") + b"\xc0\x00" + b"\xe0\x00"
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(dados)), saida)
    assert cap.comandos == ["SUBSCRIBE #"]
    assert b"\x90\x03\x00\x01\x00" in saida.dados and saida.dados.endswith(b"\xd0\x00")


async def test_connect_v5_com_propriedades(leitor_com):
    saida = Saida()
    corpo = (
        s("MQTT")
        + b"\x05"
        + b"\xc2"
        + b"\x00\x3c"
        + b"\x05\x11\x00\x00\x00\x0a"
        + s("c")
        + s("adm")
        + s("pw")
    )
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(pacote(0x10, corpo))), saida)
    assert (cap.usuario, cap.senha) == ("adm", "pw")
    assert saida.dados.startswith(b"\x20\x03\x00\x00\x00")


async def test_connect_sem_credenciais(leitor_com):
    corpo = s("MQTT") + b"\x04" + b"\x02" + b"\x00\x3c" + s("anon")
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(pacote(0x10, corpo))), Saida())
    assert cap.usuario is None and cap.senha is None


# Bordas do tamanho do pacote (auditoria final, L2): remaining length = max_pacote é aceito.
def _corpo_connect() -> bytes:
    return s("MQTT") + b"\x04" + b"\xc2" + b"\x00\x3c" + s("cli1") + s("camera") + s("123456")


async def test_pacote_do_tamanho_maximo_e_aceito(leitor_com):
    corpo = _corpo_connect()
    saida = Saida()
    servico = ServicoMqtt(max_pacote=len(corpo))
    cap = await servico.atender(LeitorLimitado(leitor_com(pacote(0x10, corpo))), saida)
    assert (cap.usuario, cap.senha) == ("camera", "123456")
    assert saida.dados.startswith(b"\x20\x02\x00\x00")  # CONNACK


async def test_pacote_um_byte_acima_do_maximo_encerra_a_sessao(leitor_com):
    corpo = _corpo_connect()
    saida = Saida()
    servico = ServicoMqtt(max_pacote=len(corpo) - 1)
    cap = await servico.atender(LeitorLimitado(leitor_com(pacote(0x10, corpo))), saida)
    assert cap.usuario is None and cap.senha is None
    assert saida.dados == b""  # nem CONNACK: o corpo nem foi lido
    assert cap.bytes_recebidos == 2  # só o cabeçalho fixo e o remaining length
