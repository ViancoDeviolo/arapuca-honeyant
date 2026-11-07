"""`honeyant-exportar-resumo`: agrega as últimas 24 h da isca num `ResumoDeAmeaca` sem IPs.

Roda na EC2, no container de leitura (`mode=ro`), e imprime o JSON:

    docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml \\
        run --rm -T --entrypoint honeyant-exportar-resumo verificar-ro > resumo-real.json

Com um caminho como argumento, grava o arquivo em vez de imprimir. O banco vem de
`HONEYANT_DB` (padrão `/dados/isca.db`). O resumo não tem nenhum IP: só contagens, as
credenciais mais tentadas e a intenção (fuzzy do intel).
"""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from honeyant.intel.adapters.sqlite_leitura import LeitorSqlite
from honeyant.intel.resumo import agregar

JANELA_HORAS = 24


def main(argv: Sequence[str] | None = None, agora: datetime | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="honeyant-exportar-resumo", description=__doc__.splitlines()[0]
    )
    p.add_argument("destino", nargs="?", type=Path, help="arquivo de saída (padrão: imprime)")
    args = p.parse_args(argv)
    agora = (agora or datetime.now(UTC)).replace(microsecond=0)
    try:
        leitor = LeitorSqlite(Path(os.environ.get("HONEYANT_DB", "/dados/isca.db")))
    except FileNotFoundError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    try:
        eventos = leitor.eventos_desde(agora - timedelta(hours=JANELA_HORAS))
        resumo = agregar(eventos, leitor.acumulado_por_servico(), agora, JANELA_HORAS)
    finally:
        leitor.fechar()
    texto = resumo.model_dump_json(indent=2) + "\n"
    if args.destino:
        args.destino.write_text(texto, encoding="utf-8")
        print(f"{resumo.total_eventos} eventos nas últimas 24 h em {args.destino}", file=sys.stderr)
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
