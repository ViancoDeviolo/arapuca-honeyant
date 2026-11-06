import os

from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.telnet import ServicoTelnet


async def nada(b):
    pass


async def test_binario_e_utf8_invalido_nao_quebram(leitor_com):
    dados = b"\xff\xfd\x03\x80\xfe\xc3(\n" + os.urandom(64).replace(b"\n", b"") + b"\n"
    cap = await ServicoTelnet().atender(LeitorLimitado(leitor_com(dados)), nada)
    assert cap.usuario is not None and "�" in cap.usuario


async def test_payload_gigante_encerra_sem_excecao(leitor_com):
    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"A" * 100_000), max_bytes=8192), nada
    )
    assert cap.bytes_recebidos <= 8192


async def test_xss_e_injecao_sao_guardados_como_texto(leitor_com):
    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"<script>alert(1)</script>\n; rm -rf / #\n$(reboot)\n")), nada
    )
    assert cap.usuario == "<script>alert(1)</script>" and cap.comandos == ["$(reboot)"]


async def test_cliente_mudo_devolve_captura_vazia(leitor_com):
    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"", eof=False), ocioso_s=0.05), nada
    )
    assert cap.usuario is None and cap.comandos == []
