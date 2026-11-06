"""Verifica, no compose real, que outro container lê o banco da isca só em mode=ro.

Uso (ao lado da isca; ver infra/aws/DEPLOY.md):
    docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml \
        run --rm verificar-ro

Imprime uma linha JSON (sem IPs) e sai com 0 só se as duas camadas da spec (seção 3)
seguram a escrita: a conexão em mode=ro e o usuário do container sem permissão de
escrita no arquivo do banco.
"""

import json
import os
from pathlib import Path
from typing import Any

from honeyant.intel.adapters.sqlite_leitura import LeitorSqlite


def relatorio(caminho: Path) -> dict[str, Any]:
    leitor = LeitorSqlite(caminho)
    try:
        return {
            "modo": leitor.modo(),
            "eventos": leitor.contar(),
            "acumulado": {s.value: n for s, n in leitor.acumulado_por_servico().items()},
            "escrita_bloqueada": leitor.escrita_bloqueada(),
            "arquivo_gravavel": os.access(caminho, os.W_OK),
        }
    finally:
        leitor.fechar()


def main() -> int:
    r = relatorio(Path(os.environ.get("HONEYANT_DB", "/dados/isca.db")))
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["escrita_bloqueada"] and not r["arquivo_gravavel"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
