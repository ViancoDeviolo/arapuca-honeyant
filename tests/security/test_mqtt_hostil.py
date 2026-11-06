from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.mqtt import ServicoMqtt


async def nada(b):
    pass


async def test_varint_com_mais_de_4_bytes_encerra(leitor_com):
    cap = await ServicoMqtt().atender(
        LeitorLimitado(leitor_com(b"\x10\xff\xff\xff\xff\x7f" + b"x" * 100)), nada
    )
    assert cap.usuario is None and cap.bytes_recebidos <= 6


async def test_remaining_length_acima_do_limite_nao_le_o_corpo(leitor_com):
    cap = await ServicoMqtt().atender(
        LeitorLimitado(leitor_com(b"\x10\xff\xff\x03" + b"x" * 70_000)), nada
    )
    assert cap.bytes_recebidos <= 4


async def test_connect_truncado_nao_lanca(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"\x10\x20\x00\x04MQ")), nada)
    assert cap.usuario is None


async def test_campo_com_tamanho_mentiroso_nao_lanca(leitor_com):
    corpo = b"\x00\x04MQTT\x04\xc2\x00\x3c\xff\xffabc"
    cap = await ServicoMqtt().atender(
        LeitorLimitado(leitor_com(bytes([0x10, len(corpo)]) + corpo)), nada
    )
    assert cap.usuario is None


async def test_primeiro_pacote_nao_connect_encerra(leitor_com):
    cap = await ServicoMqtt().atender(LeitorLimitado(leitor_com(b"GET / HTTP/1.1\r\n\r\n")), nada)
    assert cap.comandos == []
