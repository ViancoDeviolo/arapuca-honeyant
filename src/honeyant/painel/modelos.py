"""Modelos do painel (spec, seção 3.2). São do painel, não contratos do `core`."""

from datetime import datetime
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
    """O resumo exibido e de onde ele veio.

    - `ao_vivo`: acabou de chegar do resumo-api da EC2 (app ao vivo);
    - `offline`: o último resumo ao vivo guardado em cache (sem acesso à EC2);
    - `real`: o resumo real congelado em docs/demo;
    - `exemplo`: o resumo de exemplo.
    """

    origem: Literal["ao_vivo", "offline", "real", "exemplo"]
    resumo: ResumoDeAmeaca
    atualizado_em: datetime | None = None  # quando o resumo ao vivo chegou
    aviso: str | None = None  # ex.: "chave de acesso inválida"
