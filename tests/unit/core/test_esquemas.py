from pathlib import Path

from honeyant.apps.contratos import serializar
from honeyant.core.esquemas import esquemas

PASTA = Path(__file__).parents[3] / "docs" / "contratos"


def test_esquemas_versionados_estao_atualizados():
    """Se falhar: rode `uv run honeyant-contratos` e faça commit de docs/contratos/."""
    gerados = esquemas()
    assert sorted(p.name for p in PASTA.glob("*.schema.json")) == sorted(gerados)
    for nome, esquema in gerados.items():
        assert (PASTA / nome).read_text(encoding="utf-8") == serializar(esquema), nome
