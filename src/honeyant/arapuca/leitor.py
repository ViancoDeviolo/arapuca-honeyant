"""Leitura de sockets com limites de bytes e de inatividade."""

import asyncio
import time


class LimiteExcedido(Exception):
    """A sessão tentou enviar mais bytes do que o permitido."""


class LeitorLimitado:
    def __init__(
        self,
        leitor: asyncio.StreamReader,
        max_bytes: int = 8192,
        ocioso_s: float = 15.0,
        prazo_s: float | None = None,
    ) -> None:
        """`prazo_s` é a duração máxima da sessão inteira; `ocioso_s`, a espera por byte."""
        self._leitor = leitor
        self._max_bytes = max_bytes
        self._ocioso_s = ocioso_s
        self._fim = None if prazo_s is None else time.monotonic() + prazo_s
        self.bytes_lidos = 0

    def _espera(self) -> float:
        if self._fim is None:
            return self._ocioso_s
        restante = self._fim - time.monotonic()
        if restante <= 0:
            raise TimeoutError("prazo da sessão esgotado")
        return min(self._ocioso_s, restante)

    async def ler_linha(self, max_linha: int = 256) -> bytes | None:
        """Lê até `\n` (sem `\r\n`). Corta em `max_linha` e descarta o resto da linha.

        Devolve None no EOF sem dados. Lança LimiteExcedido ou TimeoutError.
        """
        linha = bytearray()
        while True:
            byte = await self._ler_byte()
            if byte is None:
                return bytes(linha) if linha else None
            if byte == b"\n":
                return bytes(linha.rstrip(b"\r"))
            if len(linha) < max_linha:
                linha += byte

    async def ler_exato(self, n: int) -> bytes:
        """Lê exatamente `n` bytes. Recusa antes de ler se isso estourar o limite."""
        if self.bytes_lidos + n > self._max_bytes:
            raise LimiteExcedido(f"{self.bytes_lidos + n} > {self._max_bytes}")
        dados = await asyncio.wait_for(self._leitor.readexactly(n), self._espera())
        self.bytes_lidos += n
        return dados

    async def _ler_byte(self) -> bytes | None:
        if self.bytes_lidos >= self._max_bytes:
            raise LimiteExcedido(f"> {self._max_bytes}")
        byte = await asyncio.wait_for(self._leitor.read(1), self._espera())
        if not byte:
            return None
        self.bytes_lidos += 1
        return byte
