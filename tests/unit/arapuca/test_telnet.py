import asyncio

import pytest

from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.telnet import ServicoTelnet, remover_iac


def test_remover_iac():
    assert remover_iac(b"\xff\xfb\x01ro\xff\xffot\xff\xfa\x18\x00\xff\xf0") == b"ro\xffot"


async def test_captura_login_senha_e_comandos(leitor_com):
    enviado = bytearray()

    async def escrever(b):
        enviado.extend(b)

    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"root\r\nxc3511\r\nuname -a\r\ncat /etc/passwd\r\nexit\r\n")),
        escrever,
    )
    assert (cap.usuario, cap.senha) == ("root", "xc3511")
    assert cap.comandos == ["uname -a", "cat /etc/passwd"]
    assert b"armv7l" in enviado and b"command not found" in enviado


@pytest.mark.parametrize(
    "fim", [b"\r\n", b"\r\x00", b"\r", b"\n"], ids=["CRLF", "CRNUL", "CR", "LF"]
)
async def test_captura_usuario_e_senha_com_qualquer_fim_de_linha(fim):
    """Antes da correção, CR NUL e CR sozinho estouravam o ocioso e a sessão ficava sem
    usuário e senha. Aqui o cliente manda cada linha e espera, como um bot faria."""
    fonte = asyncio.StreamReader()

    async def escrever(b):
        pass

    for linha in (b"root", b"xc3511", b"exit"):
        fonte.feed_data(linha + fim)
    sessao = asyncio.create_task(
        ServicoTelnet().atender(LeitorLimitado(fonte, ocioso_s=0.3), escrever)
    )
    cap = await asyncio.wait_for(sessao, timeout=2)
    assert (cap.usuario, cap.senha) == ("root", "xc3511")
    assert cap.comandos == []


async def test_para_em_20_comandos(leitor_com):
    async def escrever(b):
        pass

    cap = await ServicoTelnet().atender(
        LeitorLimitado(leitor_com(b"u\np\n" + b"ls\n" * 50)), escrever
    )
    assert len(cap.comandos) == 20


async def test_nao_ecoa_entrada_do_atacante(leitor_com):
    enviado = bytearray()

    async def escrever(b):
        enviado.extend(b)

    await ServicoTelnet().atender(LeitorLimitado(leitor_com(b"u\np\nMARCA_UNICA\n")), escrever)
    assert b"MARCA_UNICA" not in enviado
