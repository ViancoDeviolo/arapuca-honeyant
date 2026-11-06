"""Contrato EvidenciaDeRede: o que o sensor observou numa aresta da casa.

`None` em qualquer campo booleano significa "não observado". Quem consome decide o que
fazer com isso; o pathfinder assume o pior (postura conservadora).
"""

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from honeyant.core.comum import PADRAO_ARESTA, exigir_utc, separar_aresta

CAMPOS_OBSERVADOS = (
    "texto_puro",
    "credencial_vazada",
    "autenticacao_exigida",
    "acl_bloqueia",
    "alcancavel",
)


class Fonte(StrEnum):
    PASSIVO = "passivo"  # infere olhando o tráfego
    ATIVO = "ativo"  # testa de fato (honeyant verificar)


class EvidenciaDeRede(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    aresta: str = Field(pattern=PADRAO_ARESTA)
    observado_em: datetime
    fonte: Fonte
    texto_puro: bool | None = None
    credencial_vazada: bool | None = None  # senha usada/aceita está no top 20 da isca
    autenticacao_exigida: bool | None = None
    acl_bloqueia: bool | None = None
    alcancavel: bool | None = None

    @field_validator("observado_em")
    @classmethod
    def _utc(cls, valor: datetime) -> datetime:
        return exigir_utc(valor)

    @property
    def origem(self) -> str:
        return separar_aresta(self.aresta)[0]

    @property
    def destino(self) -> str:
        return separar_aresta(self.aresta)[1]


def _prioridade(e: EvidenciaDeRede) -> tuple[bool, datetime]:
    return (e.fonte is Fonte.ATIVO, e.observado_em)


def combinar_evidencias(evidencias: Iterable[EvidenciaDeRede]) -> dict[str, EvidenciaDeRede]:
    """Junta várias evidências da mesma aresta numa só, por aresta.

    Regras (spec, seção 6):
    - um valor observado sempre substitui `None`;
    - em conflito vale a evidência ativa mais recente (ela testa; a passiva só infere).

    Implementação: ordena da menos para a mais prioritária e deixa cada valor não-`None`
    sobrescrever o anterior. A evidência combinada fica com a fonte e o horário da mais
    prioritária.
    """
    por_aresta: dict[str, list[EvidenciaDeRede]] = {}
    for e in evidencias:
        por_aresta.setdefault(e.aresta, []).append(e)

    combinadas: dict[str, EvidenciaDeRede] = {}
    for aresta, lista in por_aresta.items():
        lista.sort(key=_prioridade)
        valores: dict[str, bool | None] = dict.fromkeys(CAMPOS_OBSERVADOS)
        for e in lista:
            for campo in CAMPOS_OBSERVADOS:
                valor = getattr(e, campo)
                if valor is not None:
                    valores[campo] = valor
        topo = lista[-1]
        combinadas[aresta] = EvidenciaDeRede(
            aresta=aresta, observado_em=topo.observado_em, fonte=topo.fonte, **valores
        )
    return combinadas
