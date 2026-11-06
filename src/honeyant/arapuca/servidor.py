"""Servidor asyncio da isca: aceita conexões, aplica limites e grava eventos."""

import asyncio
import contextlib
import ipaddress
import json
import logging
from datetime import UTC, datetime

from honeyant.arapuca.leitor import LeitorLimitado
from honeyant.arapuca.limites import Limitador
from honeyant.arapuca.ports import Captura, RepositorioDeEventos, ResolvedorGeo, ServicoFalso
from honeyant.core.eventos import EventoDeAtaque

log = logging.getLogger("honeyant.isca")

_FOLGA_S = 5.0  # margem do timeout externo sobre o prazo da sessão


def normalizar_ip(bruto: str) -> str:
    """'::ffff:1.2.3.4' vira '1.2.3.4', para limites e geo tratarem o mesmo IP igual."""
    ip = ipaddress.ip_address(bruto.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


class ServidorDaIsca:
    def __init__(
        self,
        servicos: dict[int, ServicoFalso],
        repositorio: RepositorioDeEventos,
        geo: ResolvedorGeo,
        limitador: Limitador,
        sessao_s: float = 60.0,
        ocioso_s: float = 15.0,
        max_bytes: int = 8192,
        # a isca precisa ouvir em todas as interfaces
        host: str = "0.0.0.0",  # noqa: S104  # nosec B104
    ) -> None:
        self._servicos = servicos
        self._repositorio = repositorio
        self._geo = geo
        self._limitador = limitador
        self._sessao_s = sessao_s
        self._ocioso_s = ocioso_s
        self._max_bytes = max_bytes
        self._host = host
        self._servidores: list[asyncio.Server] = []

    async def iniciar(self) -> dict[int, int]:
        """Abre um servidor por serviço. Devolve {porta pedida: porta real}."""
        portas: dict[int, int] = {}
        for porta, servico in self._servicos.items():
            servidor = await asyncio.start_server(
                lambda r, w, s=servico: self._atender(s, r, w), self._host, porta
            )
            self._servidores.append(servidor)
            portas[porta] = servidor.sockets[0].getsockname()[1]
        return portas

    async def parar(self) -> None:
        for servidor in self._servidores:
            servidor.close()
        for servidor in self._servidores:
            await servidor.wait_closed()
        self._servidores.clear()

    async def ciclo_de_limites(self, intervalo_s: float = 60.0) -> None:
        while True:
            await asyncio.sleep(intervalo_s)
            removidos = await asyncio.to_thread(
                self._repositorio.aplicar_limites, datetime.now(UTC)
            )
            if removidos:
                log.info(json.dumps({"acao": "limites", "removidos": removidos}))

    async def _atender(
        self, servico: ServicoFalso, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> None:
        try:
            ip = normalizar_ip(escritor.get_extra_info("peername")[0])
        except (TypeError, ValueError, IndexError):
            escritor.close()
            return
        if not self._limitador.entrar(ip):
            escritor.close()
            return
        try:
            captura = await self._conduzir(servico, leitor, escritor)
            await self._gravar(servico, ip, captura)
        except Exception:  # a isca nunca pode cair por causa de uma sessão
            log.exception("falha ao atender sessão")
        finally:
            self._limitador.sair(ip)
            escritor.close()
            with contextlib.suppress(Exception):
                await escritor.wait_closed()

    async def _conduzir(
        self, servico: ServicoFalso, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> Captura:
        limitado = LeitorLimitado(leitor, self._max_bytes, self._ocioso_s, self._sessao_s)

        async def escrever(dados: bytes) -> None:
            escritor.write(dados)
            await asyncio.wait_for(escritor.drain(), self._ocioso_s)

        try:
            async with asyncio.timeout(self._sessao_s + _FOLGA_S):
                return await servico.atender(limitado, escrever)
        except TimeoutError:
            return Captura(bytes_recebidos=limitado.bytes_lidos)

    async def _gravar(self, servico: ServicoFalso, ip: str, captura: Captura) -> None:
        pais, asn = self._geo.resolver(ip)
        evento = EventoDeAtaque(
            ts=datetime.now(UTC),
            servico=servico.servico,
            ip_origem=ip,
            pais=pais,
            asn=asn,
            usuario=captura.usuario,
            senha=captura.senha,
            comandos=captura.comandos,
            bytes_recebidos=captura.bytes_recebidos,
        )
        await asyncio.to_thread(self._repositorio.salvar, evento)
        log.info(
            json.dumps(
                {"servico": evento.servico.value, "pais": pais, "bytes": evento.bytes_recebidos}
            )
        )
