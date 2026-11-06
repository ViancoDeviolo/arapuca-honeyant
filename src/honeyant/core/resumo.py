"""Contrato ResumoDeAmeaca: o que a nuvem entrega ao notebook (GET /api/v1/resumo).

Só dados agregados. Nenhum IP (LGPD): `extra="forbid"` rejeita qualquer campo a mais.
Usuário e senha vêm de atacantes reais, então passam pela mesma higiene do evento.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from honeyant.core.comum import exigir_utc
from honeyant.core.eventos import LIMITE_CREDENCIAL, Servico
from honeyant.core.texto import limpar

LIMITE_TOP_CREDENCIAIS = 20

Contagem = Annotated[int, Field(ge=0)]
# ISO 3166-1 alfa-2. Convenção: o intel usa "ZZ" para país desconhecido.
CodigoPais = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$", to_upper=True)]
# Convenção: o intel usa ASN 0 (reservado) para ASN desconhecido.
NumeroAsn = Annotated[int, Field(ge=0)]


class Intencao(StrEnum):
    VARREDURA = "varredura"
    FORCA_BRUTA = "forca_bruta"
    BOTNET = "botnet"


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CredencialTentada(_Modelo):
    usuario: str | None = None
    senha: str | None = None
    tentativas: int = Field(ge=1)

    @field_validator("usuario", "senha", mode="before")
    @classmethod
    def _higiene(cls, valor: object) -> object:
        if isinstance(valor, str):
            return limpar(valor, LIMITE_CREDENCIAL)
        return valor


class ResumoDeAmeaca(_Modelo):
    schema_version: Literal[1] = 1
    gerado_em: datetime
    janela_horas: int = Field(default=24, gt=0)
    total_eventos: Contagem
    por_servico: dict[Servico, Contagem]  # dentro da janela (sobe e desce)
    acumulado_por_servico: dict[Servico, Contagem]  # desde o início; só cresce
    por_pais: dict[CodigoPais, Contagem]
    por_asn: dict[NumeroAsn, Contagem]
    intencao: dict[Intencao, Contagem]
    top_credenciais: list[CredencialTentada] = Field(max_length=LIMITE_TOP_CREDENCIAIS)

    @field_validator("gerado_em")
    @classmethod
    def _utc(cls, valor: datetime) -> datetime:
        return exigir_utc(valor)

    @model_validator(mode="after")
    def _soma_bate(self) -> Self:
        if sum(self.por_servico.values()) != self.total_eventos:
            raise ValueError("a soma de por_servico precisa ser igual a total_eventos")
        return self
