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
