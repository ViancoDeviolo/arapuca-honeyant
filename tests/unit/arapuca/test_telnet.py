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
