import asyncio
import contextlib

import pytest

from honeyant.arapuca.adapters.geo import GeoNulo
from honeyant.arapuca.adapters.memoria import RepositorioEmMemoria
from honeyant.arapuca.limites import Limitador
from honeyant.arapuca.mqtt import ServicoMqtt
from honeyant.arapuca.servidor import ServidorDaIsca
from honeyant.arapuca.telnet import ServicoTelnet
from honeyant.core.eventos import Servico

pytestmark = pytest.mark.integration


class RepoQueGuarda(RepositorioEmMemoria):
    """Guarda os eventos salvos para o teste inspecionar."""

    def __init__(self):
        super().__init__()
        self.salvos = []

    def salvar(self, evento):
        super().salvar(evento)
        self.salvos.append(evento)


@pytest.fixture
async def isca():
    repo = RepositorioEmMemoria()
    srv = ServidorDaIsca(
        {0: ServicoTelnet()}, repo, GeoNulo(), Limitador(max_por_ip=1), ocioso_s=0.2
    )
    portas = await srv.iniciar()
    yield srv, repo, portas[0]
    await srv.parar()


async def test_sessao_telnet_vira_evento(isca):
    _, repo, porta = isca
    r, w = await asyncio.open_connection("127.0.0.1", porta)
    w.write(b"root\r\nvizxv\r\nexit\r\n")
    await w.drain()
    await r.read()  # servidor fecha
    await asyncio.sleep(0.1)
    assert repo.contar() == 1 and repo.acumulado_por_servico()[Servico.TELNET] == 1


async def test_cliente_mudo_e_encerrado_e_libera_vaga(isca):
    _, repo, porta = isca
    r, w = await asyncio.open_connection("127.0.0.1", porta)
    await asyncio.wait_for(r.read(), timeout=2)  # fechado pelo tempo ocioso
    await asyncio.sleep(0.1)
    r2, w2 = await asyncio.open_connection("127.0.0.1", porta)  # vaga do IP foi liberada
    w2.write(b"a\nb\nexit\n")
    await w2.drain()
    await r2.read()
    await asyncio.sleep(0.1)
    assert repo.contar() == 2  # a sessão muda também gera evento (varredura)


async def test_prazo_da_sessao_preserva_o_que_foi_capturado():
    repo = RepoQueGuarda()
    srv = ServidorDaIsca({0: ServicoTelnet()}, repo, GeoNulo(), Limitador(), sessao_s=0.5)
    porta = (await srv.iniciar())[0]
    r, w = await asyncio.open_connection("127.0.0.1", porta)
    w.write(b"root\nsenha\n")
    await w.drain()
    with contextlib.suppress(ConnectionError):  # o servidor fecha ao fim do prazo
        for _ in range(10):  # um comando a cada 0.1 s: nunca ocioso, mas estoura o prazo
            w.write(b"ls\n")
            await w.drain()
            await asyncio.sleep(0.1)
        await asyncio.wait_for(r.read(), timeout=2)
    await asyncio.sleep(0.1)
    await srv.parar()
    assert len(repo.salvos) == 1
    assert repo.salvos[0].usuario == "root" and len(repo.salvos[0].comandos) >= 3


async def test_conexao_recusada_pelo_limitador_nao_gera_evento():
    repo = RepositorioEmMemoria()
    srv = ServidorDaIsca({0: ServicoMqtt()}, repo, GeoNulo(), Limitador(taxa_por_minuto=1))
    porta = (await srv.iniciar())[0]
    for _ in range(3):
        r, w = await asyncio.open_connection("127.0.0.1", porta)
        with contextlib.suppress(ConnectionError):  # recusadas são fechadas na hora
            w.write(b"\xe0\x00")
            await w.drain()
            await asyncio.wait_for(r.read(), timeout=2)
    await asyncio.sleep(0.1)
    await srv.parar()
    assert repo.contar() == 1
