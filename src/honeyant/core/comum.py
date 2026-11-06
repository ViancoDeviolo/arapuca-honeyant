"""Peças compartilhadas pelos contratos: identificadores, chave de aresta e horário UTC."""

import re
from datetime import UTC, datetime

# Id de nó: minúsculas, dígitos e "_", começando por letra. Curto e seguro para usar
# como chave JSON, atributo SVG ou nome de tópico, sem precisar escapar.
PADRAO_ID = r"^[a-z][a-z0-9_]{0,31}$"
PADRAO_ARESTA = r"^[a-z][a-z0-9_]{0,31}->[a-z][a-z0-9_]{0,31}$"
_ARESTA = re.compile(PADRAO_ARESTA)


def chave_aresta(origem: str, destino: str) -> str:
    """Forma canônica de uma aresta dirigida: "origem->destino"."""
    return f"{origem}->{destino}"


def separar_aresta(chave: str) -> tuple[str, str]:
    if not _ARESTA.match(chave):
        raise ValueError(f"aresta mal formada: {chave!r}")
    origem, destino = chave.split("->")
    return origem, destino


def exigir_utc(valor: datetime) -> datetime:
    if valor.tzinfo is None:
        raise ValueError("horário precisa ter fuso horário")
    return valor.astimezone(UTC)
