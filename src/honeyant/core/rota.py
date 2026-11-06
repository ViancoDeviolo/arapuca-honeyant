"""Contratos Rota e Snapshot: o que o pathfinder entrega ao painel."""

import math
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from honeyant.core.comum import PADRAO_ARESTA, PADRAO_ID, chave_aresta

LIMITE_CAMINHOS = 20

IdDeNo = Annotated[str, StringConstraints(pattern=PADRAO_ID)]
ChaveDeAresta = Annotated[str, StringConstraints(pattern=PADRAO_ARESTA)]


class Algoritmo(StrEnum):
    ACO = "aco"
    DIJKSTRA = "dijkstra"


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Rota(_Modelo):
    """Caminho da internet até o alvo.

    `custo` é a soma de −ln(risco) das arestas; `plausibilidade = e^(−custo)` é o
    produto dos riscos: um score para comparar rotas, não uma probabilidade calibrada.
    """

    nos: list[IdDeNo] = Field(min_length=2)
    custo: float = Field(ge=0, allow_inf_nan=False)
    plausibilidade: float = Field(ge=0, le=1)
    algoritmo: Algoritmo

    @property
    def arestas(self) -> list[str]:
        return [chave_aresta(a, b) for a, b in zip(self.nos, self.nos[1:], strict=False)]

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if len(set(self.nos)) != len(self.nos):
            raise ValueError("rota não pode repetir nó")
        if not math.isclose(self.plausibilidade, math.exp(-self.custo), rel_tol=1e-6):
            raise ValueError("plausibilidade precisa ser e^(-custo)")
        return self


class Snapshot(_Modelo):
    """Estado do ACO numa iteração, para o formigueiro desenhar (e para o replay)."""

    schema_version: Literal[1] = 1
    execucao_id: UUID
    semente: int
    iteracao: int = Field(ge=0)
    feromonio: dict[ChaveDeAresta, Annotated[float, Field(ge=0, allow_inf_nan=False)]]
    caminhos: list[list[IdDeNo]] = Field(max_length=LIMITE_CAMINHOS)
    melhor: Rota | None = None
