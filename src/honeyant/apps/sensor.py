"""`honeyant-sensor`: lê um `.pcap` da casa e grava as evidências de rede em JSON.

    uv run honeyant-sensor docs/capturas/antes.pcap
    uv run honeyant-sensor docs/capturas/antes.pcap --saida evidencias-sensor.json

Usa o perfil da casa (para saber quais arestas existem) e o mesmo resumo do painel (para
saber se a senha que passou em claro é uma credencial conhecida: as completas do resumo
real ∪ as padrão de fábrica de IoT, em `core/credenciais.py`).
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from honeyant.apps.local import FonteDoResumoLocal, _ler_json
from honeyant.core.casa import PerfilDaCasa
from honeyant.core.credenciais import credenciais_conhecidas
from honeyant.sensor.adapters.pcap import FormatoNaoSuportado, LeitorPcap
from honeyant.sensor.detector import detectar


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="honeyant-sensor", description=__doc__.splitlines()[0])
    p.add_argument("pcap", type=Path, help="arquivo .pcap (formato clássico do tcpdump)")
    p.add_argument("--saida", type=Path, help="grava o JSON aqui (padrão: imprime na tela)")
    p.add_argument("--demo-dir", type=Path, default=Path("docs/demo"))
    p.add_argument("--perfil", default="inseguro", help="topologia da casa (padrão: inseguro)")
    args = p.parse_args(argv)

    perfil = PerfilDaCasa.model_validate(_ler_json(args.demo_dir / f"perfil-{args.perfil}.json"))
    resumo = FonteDoResumoLocal(args.demo_dir).resumo().resumo
    vazadas = credenciais_conhecidas(resumo)
    try:
        evidencias = detectar(LeitorPcap(args.pcap), perfil, vazadas)
    except (FormatoNaoSuportado, OSError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    texto = json.dumps([e.model_dump(mode="json") for e in evidencias], indent=2) + "\n"
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
        print(f"{len(evidencias)} evidência(s) em {args.saida}", file=sys.stderr)
    else:
        sys.stdout.write(texto)
    for e in evidencias:
        vazada = " e credencial vazada" if e.credencial_vazada else ""
        print(f"  {e.aresta}: MQTT em texto puro{vazada}", file=sys.stderr)
    if not evidencias:
        print("  nenhum MQTT em texto puro", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
