"""JSON Schema de cada contrato, para quem consome sem Python (ex.: o JS do painel)."""

from typing import Any

from pydantic import BaseModel

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.eventos import EventoDeAtaque
from honeyant.core.evidencia import EvidenciaDeRede
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Rota, Snapshot

CONTRATOS: tuple[type[BaseModel], ...] = (
    EventoDeAtaque,
    ResumoDeAmeaca,
    PerfilDaCasa,
    EvidenciaDeRede,
    Rota,
    Snapshot,
)


def esquemas() -> dict[str, dict[str, Any]]:
    """Nome do arquivo → JSON Schema. Função pura: quem grava no disco é `apps`."""
    return {f"{m.__name__}.schema.json": m.model_json_schema() for m in CONTRATOS}
