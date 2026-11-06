"""Telnet falso de baixa interação: pede login, finge um shell e só registra."""

import asyncio

from honeyant.arapuca.leitor import LeitorLimitado, LimiteExcedido
from honeyant.arapuca.ports import Captura, Escrever
from honeyant.core.eventos import LIMITE_COMANDOS, Servico

IAC, SB, SE = 255, 250, 240
_COMANDOS_COM_OPCAO = range(251, 255)  # WILL, WONT, DO, DONT

_RESPOSTAS = {
    "uname -a": b"Linux camera 3.10.14 #1 PREEMPT armv7l GNU/Linux\r\n",
    "whoami": b"root\r\n",
}
_DESCONHECIDO = b"-sh: command not found\r\n"
_SAIR = {"exit", "logout"}


def remover_iac(dados: bytes) -> bytes:
    """Remove a negociação Telnet (IAC). `IAC IAC` vira um byte 255 literal."""
    saida = bytearray()
    i = 0
    while i < len(dados):
        byte = dados[i]
        if byte != IAC:
            saida.append(byte)
            i += 1
            continue
        comando = dados[i + 1] if i + 1 < len(dados) else None
        if comando == IAC:
            saida.append(IAC)
            i += 2
        elif comando in _COMANDOS_COM_OPCAO:
            i += 3
        elif comando == SB:
            fim = dados.find(bytes([IAC, SE]), i + 2)
            i = len(dados) if fim == -1 else fim + 2
        else:
            i += 2
    return bytes(saida)


def _texto(linha: bytes) -> str:
    return remover_iac(linha).decode("utf-8", errors="replace")


class ServicoTelnet:
    servico = Servico.TELNET

    async def atender(self, leitor: LeitorLimitado, escrever: Escrever) -> Captura:
        captura = Captura()
        try:
            await self._conduzir(leitor, escrever, captura)
        except (LimiteExcedido, TimeoutError, ConnectionError, asyncio.IncompleteReadError):
            pass
        captura.bytes_recebidos = leitor.bytes_lidos
        return captura

    async def _conduzir(self, leitor: LeitorLimitado, escrever: Escrever, cap: Captura) -> None:
        await escrever(b"\r\nlogin: ")
        if (linha := await leitor.ler_linha()) is None:
            return
        cap.usuario = _texto(linha)
        await escrever(b"Password: ")
        if (linha := await leitor.ler_linha()) is None:
            return
        cap.senha = _texto(linha)
        await escrever(b"\r\n$ ")
        while len(cap.comandos) < LIMITE_COMANDOS:
            if (linha := await leitor.ler_linha()) is None:
                return
            comando = _texto(linha).strip()
            if comando in _SAIR:
                return
            cap.comandos.append(comando)
            await escrever(_RESPOSTAS.get(comando, _DESCONHECIDO) + b"$ ")
