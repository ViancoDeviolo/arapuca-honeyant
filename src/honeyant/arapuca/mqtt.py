"""MQTT falso: aceita qualquer CONNECT, registra credenciais, PUBLISH e SUBSCRIBE.

Suporta MQTT 3.1.1 (nível 4) e 5. Nenhuma mensagem é entregue a ninguém.
"""

import asyncio
import struct

from honeyant.arapuca.leitor import LeitorLimitado, LimiteExcedido
from honeyant.arapuca.ports import Captura, Escrever
from honeyant.core.eventos import LIMITE_COMANDOS, Servico

CONNECT, PUBLISH, SUBSCRIBE, PINGREQ, DISCONNECT = 1, 3, 8, 12, 14
_FLAG_USUARIO, _FLAG_SENHA, _FLAG_WILL = 0x80, 0x40, 0x04
_PINGRESP = b"\xd0\x00"


async def ler_varint(leitor: LeitorLimitado) -> int:
    """Lê o 'remaining length' (até 4 bytes, 7 bits cada)."""
    valor = 0
    for posicao in range(4):
        byte = (await leitor.ler_exato(1))[0]
        valor |= (byte & 0x7F) << (7 * posicao)
        if not byte & 0x80:
            return valor
    raise LimiteExcedido("varint com mais de 4 bytes")


class _Cursor:
    """Leitura sequencial de um corpo de pacote já em memória."""

    def __init__(self, dados: bytes) -> None:
        self._dados = memoryview(dados)
        self._pos = 0

    def bytes_(self, n: int) -> bytes:
        if self._pos + n > len(self._dados):
            raise ValueError("campo além do fim do pacote")
        trecho = self._dados[self._pos : self._pos + n].tobytes()
        self._pos += n
        return trecho

    def u8(self) -> int:
        return self.bytes_(1)[0]

    def u16(self) -> int:
        return struct.unpack("!H", self.bytes_(2))[0]

    def binario(self) -> bytes:
        return self.bytes_(self.u16())

    def texto(self) -> str:
        return self.binario().decode("utf-8", errors="replace")

    def varint(self) -> int:
        valor = 0
        for posicao in range(4):
            byte = self.u8()
            valor |= (byte & 0x7F) << (7 * posicao)
            if not byte & 0x80:
                return valor
        raise ValueError("varint com mais de 4 bytes")

    def pular_propriedades(self) -> None:
        self.bytes_(self.varint())


class ServicoMqtt:
    servico = Servico.MQTT

    def __init__(self, max_pacote: int = 4096) -> None:
        self._max_pacote = max_pacote

    async def atender(self, leitor: LeitorLimitado, escrever: Escrever) -> Captura:
        captura = Captura()
        try:
            await self._conduzir(leitor, escrever, captura)
        except (
            LimiteExcedido,
            TimeoutError,
            ValueError,
            ConnectionError,
            asyncio.IncompleteReadError,
        ):
            pass
        captura.bytes_recebidos = leitor.bytes_lidos
        return captura

    async def _ler_pacote(self, leitor: LeitorLimitado) -> tuple[int, int, bytes]:
        cabecalho = (await leitor.ler_exato(1))[0]
        tamanho = await ler_varint(leitor)
        if tamanho > self._max_pacote:
            raise LimiteExcedido(f"pacote de {tamanho} bytes")
        corpo = await leitor.ler_exato(tamanho) if tamanho else b""
        return cabecalho >> 4, cabecalho & 0x0F, corpo

    async def _conduzir(self, leitor: LeitorLimitado, escrever: Escrever, cap: Captura) -> None:
        tipo, _, corpo = await self._ler_pacote(leitor)
        if tipo != CONNECT:
            return
        nivel = self._ler_connect(_Cursor(corpo), cap)
        await escrever(b"\x20\x03\x00\x00\x00" if nivel == 5 else b"\x20\x02\x00\x00")
        while len(cap.comandos) < LIMITE_COMANDOS:
            tipo, _, corpo = await self._ler_pacote(leitor)
            cursor = _Cursor(corpo)
            if tipo == PUBLISH:
                cap.comandos.append(f"PUBLISH {cursor.texto()}")
            elif tipo == SUBSCRIBE:
                id_pacote = cursor.u16()
                if nivel == 5:
                    cursor.pular_propriedades()
                cap.comandos.append(f"SUBSCRIBE {cursor.texto()}")
                await escrever(self._suback(id_pacote, nivel))
            elif tipo == PINGREQ:
                await escrever(_PINGRESP)
            else:  # DISCONNECT ou qualquer outro tipo encerra a sessão
                return

    @staticmethod
    def _ler_connect(cursor: _Cursor, cap: Captura) -> int:
        cursor.texto()  # nome do protocolo ("MQTT" ou "MQIsdp")
        nivel = cursor.u8()
        flags = cursor.u8()
        cursor.u16()  # keep alive
        if nivel == 5:
            cursor.pular_propriedades()
        cursor.texto()  # client id
        if flags & _FLAG_WILL:
            if nivel == 5:
                cursor.pular_propriedades()
            cursor.texto()  # will topic
            cursor.binario()  # will payload
        if flags & _FLAG_USUARIO:
            cap.usuario = cursor.texto()
        if flags & _FLAG_SENHA:
            cap.senha = cursor.binario().decode("utf-8", errors="replace")
        return nivel

    @staticmethod
    def _suback(id_pacote: int, nivel: int) -> bytes:
        if nivel == 5:
            return b"\x90\x04" + struct.pack("!H", id_pacote) + b"\x00\x00"
        return b"\x90\x03" + struct.pack("!H", id_pacote) + b"\x00"
