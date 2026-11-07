"""Leitura do pacote `CONNECT` do MQTT (3.1, 3.1.1 e 5), sem biblioteca externa.

Só o que o sensor precisa: o id do cliente e, se vierem, usuário e senha. Bytes que não
formam um `CONNECT` válido devolvem `None`, nunca uma exceção (o tráfego é hostil).
"""

import struct
from dataclasses import dataclass

_CONNECT = 0x10
_PROTOCOLOS = {(b"MQTT", 4), (b"MQTT", 5), (b"MQIsdp", 3)}


@dataclass(frozen=True)
class ConnectMqtt:
    versao: int
    id_cliente: str
    usuario: str | None
    senha: str | None


class _Fim(Exception):
    pass


class _Leitor:
    def __init__(self, dados: bytes) -> None:
        self.dados, self.pos = dados, 0

    def byte(self) -> int:
        if self.pos >= len(self.dados):
            raise _Fim
        self.pos += 1
        return self.dados[self.pos - 1]

    def bytes_(self, n: int) -> bytes:
        if self.pos + n > len(self.dados):
            raise _Fim
        self.pos += n
        return self.dados[self.pos - n : self.pos]

    def u16(self) -> int:
        return struct.unpack(">H", self.bytes_(2))[0]

    def varint(self) -> int:
        valor, mult = 0, 1
        for _ in range(4):
            b = self.byte()
            valor += (b & 0x7F) * mult
            if not b & 0x80:
                return valor
            mult *= 128
        raise _Fim  # mais de 4 bytes: inválido pelo padrão

    def texto(self) -> str:
        return self.bytes_(self.u16()).decode("utf-8", errors="replace")


def ler_connect(dados: bytes) -> ConnectMqtt | None:
    if not dados or dados[0] != _CONNECT:
        return None
    try:
        r = _Leitor(dados)
        r.byte()
        restante = r.varint()
        r = _Leitor(r.bytes_(restante))
        nome = r.bytes_(r.u16())
        versao = r.byte()
        if (nome, versao) not in _PROTOCOLOS:
            return None
        flags = r.byte()
        r.u16()  # keep alive
        if versao == 5:
            r.bytes_(r.varint())  # propriedades do CONNECT
        id_cliente = r.texto()
        if flags & 0x04:  # will
            if versao == 5:
                r.bytes_(r.varint())  # propriedades do will
            r.texto()
            r.bytes_(r.u16())
        usuario = r.texto() if flags & 0x80 else None
        senha = r.bytes_(r.u16()).decode("utf-8", errors="replace") if flags & 0x40 else None
    except _Fim:
        return None
    return ConnectMqtt(versao, id_cliente, usuario, senha)
