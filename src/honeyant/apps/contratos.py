"""Grava o JSON Schema dos contratos em docs/contratos/.

Uso: uv run honeyant-contratos [pasta]   (padrão: docs/contratos)
O teste tests/unit/core/test_esquemas.py falha se os arquivos estiverem desatualizados.
"""

import json
import sys
from pathlib import Path

from honeyant.core.esquemas import esquemas


def serializar(esquema: dict) -> str:
    return json.dumps(esquema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/contratos")
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, esquema in esquemas().items():
        (pasta / nome).write_text(serializar(esquema), encoding="utf-8", newline="\n")
        print(pasta / nome)


if __name__ == "__main__":
    main()
