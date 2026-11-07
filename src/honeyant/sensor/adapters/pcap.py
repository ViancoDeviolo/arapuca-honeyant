"""Leitor de `.pcap` (formato clássico do libpcap/tcpdump), sem biblioteca externa.

Entende os enlaces que a demo usa: Ethernet (1), Linux "cooked" SLL (113) e SLL2 (276,
o que o `tcpdump -i any` grava), além de IP puro (101). Lê IPv4 e IPv6 com TCP e devolve
só os segmentos com dados. Não remonta fluxos TCP: cada segmento é analisado sozinho, o
que basta para o `CONNECT` do MQTT, que cabe num segmento.

Arquivo malformado ou truncado nunca derruba o sensor: o pacote ruim é pulado e a
leitura para no fim do que for legível.
"""

import struct
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from honeyant.sensor.ports import SegmentoTcp

_MAGICOS = {
    0xA1B2C3D4: ("<", 1e-6),
    0xD4C3B2A1: (">", 1e-6),
    0xA1B23C4D: ("<", 1e-9),
    0x4D3CB2A1: (">", 1e-9),
}
_PCAPNG = 0x0A0D0D0A
ETHERNET, RAW, SLL, SLL2 = 1, 101, 113, 276
_IPV4, _IPV6, _VLAN = 0x0800, 0x86DD, 0x8100
_TCP = 6


class FormatoNaoSuportado(ValueError):
    """O arquivo não é um .pcap clássico ou usa um enlace que o sensor não lê."""


def _carga_ip(enlace: int, quadro: bytes) -> tuple[int, bytes] | None:
    """(ethertype, pacote IP) a partir do quadro do enlace, ou None se não for IP."""
    if enlace == ETHERNET:
        if len(quadro) < 14:
            return None
        tipo, inicio = struct.unpack_from(">H", quadro, 12)[0], 14
        if tipo == _VLAN and len(quadro) >= 18:
            tipo, inicio = struct.unpack_from(">H", quadro, 16)[0], 18
        return tipo, quadro[inicio:]
    if enlace == SLL:
        return (struct.unpack_from(">H", quadro, 14)[0], quadro[16:]) if len(quadro) >= 16 else None
    if enlace == SLL2:
        return (struct.unpack_from(">H", quadro, 0)[0], quadro[20:]) if len(quadro) >= 20 else None
    if enlace == RAW and quadro:
        versao = quadro[0] >> 4
        return ({4: _IPV4, 6: _IPV6}.get(versao, 0), quadro)
    return None


def _segmento(tipo: int, ip: bytes, instante: datetime) -> SegmentoTcp | None:
    if tipo == _IPV4 and len(ip) >= 20:
        cabecalho = (ip[0] & 0x0F) * 4
        total = struct.unpack_from(">H", ip, 2)[0]
        if ip[9] != _TCP or cabecalho < 20:
            return None
        origem, destino = ".".join(map(str, ip[12:16])), ".".join(map(str, ip[16:20]))
        tcp = ip[cabecalho : total or len(ip)]
    elif tipo == _IPV6 and len(ip) >= 40:
        if ip[6] != _TCP:  # sem cabeçalhos de extensão (a rede da demo não usa)
            return None
        origem = ":".join(f"{x:04x}" for x in struct.unpack_from(">8H", ip, 8))
        destino = ":".join(f"{x:04x}" for x in struct.unpack_from(">8H", ip, 24))
        tcp = ip[40 : 40 + struct.unpack_from(">H", ip, 4)[0]]
    else:
        return None
    if len(tcp) < 20:
        return None
    porta_origem, porta_destino = struct.unpack_from(">HH", tcp, 0)
    deslocamento = (tcp[12] >> 4) * 4
    dados = tcp[deslocamento:]
    if deslocamento < 20 or not dados:
        return None
    return SegmentoTcp(instante, origem, porta_origem, destino, porta_destino, bytes(dados))


class LeitorPcap:
    """Adapter `FonteDeTrafego` para um arquivo `.pcap`."""

    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)

    def segmentos(self) -> Iterator[SegmentoTcp]:
        dados = self.caminho.read_bytes()
        if len(dados) < 24:
            raise FormatoNaoSuportado(f"{self.caminho}: curto demais para um .pcap")
        magico = struct.unpack_from("<I", dados, 0)[0]
        if magico == _PCAPNG:
            raise FormatoNaoSuportado(
                f"{self.caminho}: é pcapng; grave com tcpdump -w (pcap clássico) "
                "ou converta com: editcap -F pcap entrada.pcapng saida.pcap"
            )
        if magico not in _MAGICOS:
            raise FormatoNaoSuportado(f"{self.caminho}: não é um arquivo .pcap")
        ordem, unidade = _MAGICOS[magico]
        enlace = struct.unpack_from(f"{ordem}I", dados, 20)[0]
        if enlace not in (ETHERNET, RAW, SLL, SLL2):
            raise FormatoNaoSuportado(f"{self.caminho}: enlace {enlace} não suportado")

        pos = 24
        while pos + 16 <= len(dados):
            segundos, fracao, gravado, _ = struct.unpack_from(f"{ordem}IIII", dados, pos)
            pos += 16
            quadro = dados[pos : pos + gravado]
            pos += gravado
            if len(quadro) < gravado:
                return  # arquivo truncado: para no último pacote inteiro
            carga = _carga_ip(enlace, quadro)
            if carga is None:
                continue
            instante = datetime.fromtimestamp(segundos + fracao * unidade, UTC)
            segmento = _segmento(carga[0], carga[1], instante)
            if segmento is not None:
                yield segmento
