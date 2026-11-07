import pytest

from honeyant.arapuca.leitor import LeitorLimitado, LimiteExcedido


async def test_le_linhas_sem_crlf(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"root\r\nadmin\n"))
    assert await leitor.ler_linha() == b"root"
    assert await leitor.ler_linha() == b"admin"
    assert await leitor.ler_linha() is None


async def test_linha_longa_e_cortada(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"x" * 500 + b"\n"))
    assert len(await leitor.ler_linha(max_linha=256)) == 256


async def test_estoura_limite_de_bytes(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"a\n" * 100), max_bytes=50)
    with pytest.raises(LimiteExcedido):
        while await leitor.ler_linha() is not None:
            pass


async def test_ocioso_gera_timeout(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"", eof=False), ocioso_s=0.05)
    with pytest.raises(TimeoutError):
        await leitor.ler_linha()


async def test_prazo_total_gera_timeout_mesmo_com_dados_chegando():
    import asyncio

    fonte = asyncio.StreamReader()
    leitor = LeitorLimitado(fonte, ocioso_s=5.0, prazo_s=0.2)

    async def alimentar():
        for _ in range(10):
            fonte.feed_data(b"x\n")
            await asyncio.sleep(0.05)

    tarefa = asyncio.create_task(alimentar())
    with pytest.raises(TimeoutError):
        while True:
            await leitor.ler_linha()
    tarefa.cancel()


# ---------- fins de linha da RFC 854: "\r\n", "\r\0", "\r" sozinho e "\n" ----------


@pytest.mark.parametrize("fim", [b"\r\n", b"\r\0", b"\r", b"\n"], ids=["CRLF", "CRNUL", "CR", "LF"])
async def test_cada_fim_de_linha_separa_usuario_e_senha(leitor_com, fim):
    leitor = LeitorLimitado(leitor_com(b"root" + fim + b"xc3511" + fim))
    assert await leitor.ler_linha() == b"root"
    assert await leitor.ler_linha() == b"xc3511"
    assert await leitor.ler_linha() is None  # sem linha vazia extra


@pytest.mark.parametrize("fim", [b"\r\n", b"\r\0", b"\r", b"\n"], ids=["CRLF", "CRNUL", "CR", "LF"])
async def test_bytes_chegando_um_a_um(fim):
    import asyncio

    fonte = asyncio.StreamReader()
    leitor = LeitorLimitado(fonte, ocioso_s=1.0)
    for b in b"admin" + fim + b"1234" + fim:
        fonte.feed_data(bytes([b]))
    fonte.feed_eof()
    assert [await leitor.ler_linha(), await leitor.ler_linha()] == [b"admin", b"1234"]
    assert await leitor.ler_linha() is None


async def test_cr_no_fim_do_buffer_entrega_a_linha_sem_esperar():
    """Cliente que manda "root\r" e fica esperando o prompt: não pode estourar o ocioso."""
    import asyncio

    fonte = asyncio.StreamReader()
    leitor = LeitorLimitado(fonte, ocioso_s=0.2)
    fonte.feed_data(b"root\r")
    assert await leitor.ler_linha() == b"root"
    # O "\n" que chega depois pertence ao "\r" anterior e não vira linha vazia.
    fonte.feed_data(b"\nsenha\r\n")
    fonte.feed_eof()
    assert await leitor.ler_linha() == b"senha"
    assert await leitor.ler_linha() is None


async def test_linha_vazia_continua_sendo_linha_vazia(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"\r\n\nfim\n"))
    assert [await leitor.ler_linha() for _ in range(3)] == [b"", b"", b"fim"]


async def test_cr_seguido_de_texto_comeca_outra_linha(leitor_com):
    leitor = LeitorLimitado(leitor_com(b"a\rb\n"))
    assert [await leitor.ler_linha(), await leitor.ler_linha()] == [b"a", b"b"]
