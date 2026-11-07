"""Modelos do painel (spec, seção 3.2). São do painel, não contratos do `core`."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import ChaveDeAresta, IdDeNo, Rota

Risco = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AnaliseDeRota(_Modelo):
    """Rota oficial (Dijkstra) de um perfil, com o que o painel precisa para desenhá-la."""

    rota: Rota | None
    riscos: dict[ChaveDeAresta, Risco]  # só as arestas da rota
    riscos_por_no: dict[IdDeNo, Risco]  # maior risco entre as arestas que tocam o nó
    bloqueadas: list[ChaveDeAresta]  # bloqueadas pelas evidências (lista explícita)


class ResumoComOrigem(_Modelo):
    """O resumo exibido e de onde ele veio: isca real (congelado) ou exemplo."""

    origem: Literal["real", "exemplo"]
    resumo: ResumoDeAmeaca
