"""Porta do sensor: de onde vem o tráfego (Adapter).

Hoje a fonte é um arquivo `.pcap` (`adapters/pcap.py`). Uma interface ao vivo seria outro
adapter com o mesmo `segmentos()`, sem mudar o detector.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SegmentoTcp:
    """Um segmento TCP com dados (payload não vazio)."""

    instante: datetime  # UTC
    origem: str
    porta_origem: int
    destino: str
    porta_destino: int
    dados: bytes


class FonteDeTrafego(Protocol):
    def segmentos(self) -> Iterator[SegmentoTcp]: ...
