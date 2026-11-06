"""Contrato EventoDeAtaque: o que a isca registra a cada sessão."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from honeyant.core.texto import limpar

LIMITE_CREDENCIAL = 64
LIMITE_COMANDOS = 20
LIMITE_COMANDO = 256

_PAIS = re.compile(r"^[A-Za-z]{2}$")


class Servico(StrEnum):
    TELNET = "telnet"
    MQTT = "mqtt"
    HTTP = "http"
    UPNP = "upnp"
    LAN = "lan"


class EventoDeAtaque(BaseModel):
    """Uma sessão recebida pela isca. Contém dado pessoal (IP): nunca sai da EC2."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    id: UUID = Field(default_factory=uuid4)
    ts: datetime
    servico: Servico
    ip_origem: IPv4Address | IPv6Address
    pais: str | None = None
    asn: int | None = None
    usuario: str | None = None
    senha: str | None = None
    comandos: list[str] = Field(default_factory=list)
    bytes_recebidos: int = Field(default=0, ge=0)

    @field_validator("usuario", "senha", mode="before")
    @classmethod
    def _truncar_credencial(cls, valor: object) -> object:
        if isinstance(valor, str):
            return limpar(valor, LIMITE_CREDENCIAL)
        return valor

    @field_validator("comandos", mode="before")
    @classmethod
    def _truncar_comandos(cls, valor: object) -> object:
        if isinstance(valor, list):
            return [limpar(str(c), LIMITE_COMANDO) for c in valor[:LIMITE_COMANDOS]]
        return valor

    @field_validator("ts")
    @classmethod
    def _exigir_utc(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None:
            raise ValueError("ts precisa ter fuso horário")
        return valor.astimezone(UTC)

    @field_validator("ip_origem")
    @classmethod
    def _desmapear_ipv4(cls, valor: IPv4Address | IPv6Address) -> IPv4Address | IPv6Address:
        if isinstance(valor, IPv6Address) and valor.ipv4_mapped is not None:
            return valor.ipv4_mapped
        return valor

    @field_validator("pais")
    @classmethod
    def _normalizar_pais(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        if not _PAIS.match(valor):
            raise ValueError("pais deve ser código ISO 3166-1 alfa-2")
        return valor.upper()
