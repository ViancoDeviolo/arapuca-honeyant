"""`honeyant-capturar`: grava `docs/capturas/antes.pcap` e `docs/capturas/depois.pcap`.

    uv run honeyant-twin preparar      # uma vez (gera senhas e certificados de teste)
    uv run honeyant-capturar           # ~1 min: perfil inseguro, depois o seguro

Para cada perfil: sobe o broker com o tcpdump (container de captura na interface do
broker, o único jeito de ver o tráfego entre containers no Docker Desktop do Windows),
espera um pouco, sobe os dispositivos, deixa a casa conversar e para o tcpdump. Os
`CONNECT` acontecem com os dispositivos já sendo gravados.

As capturas só têm credenciais **de teste geradas para a demo** (a da câmera é a padrão de
fábrica `admin`/`admin`, pública), nunca senhas reais de alguém.
"""

import argparse
import shutil
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from honeyant.apps.twin import ControleDoTwin, ErroDoTwin
from honeyant.core.casa import TipoDePerfil

DESTINO = Path("docs/capturas")
NOMES = {TipoDePerfil.INSEGURO: "antes", TipoDePerfil.SEGURO: "depois"}


def capturar(
    twin: ControleDoTwin,
    tipo: TipoDePerfil,
    destino: Path,
    duracao_s: float = 15,
    dormir: Callable[[float], None] = time.sleep,
) -> Path:
    bruto = twin.dir / "capturas" / f"{tipo.value}.pcap"
    bruto.unlink(missing_ok=True)
    twin.descer()
    twin.subir(tipo, ["broker", "captura"], captura=True)
    dormir(3)  # o tcpdump abre a interface antes do primeiro CONNECT
    twin.subir(tipo, captura=True)
    dormir(duracao_s)
    twin.parar(tipo, ["captura"])
    if not bruto.is_file() or bruto.stat().st_size == 0:
        raise ErroDoTwin(f"o tcpdump não gravou nada em {bruto}")
    destino.mkdir(parents=True, exist_ok=True)
    final = destino / f"{NOMES[tipo]}.pcap"
    shutil.copyfile(bruto, final)
    return final


def main(argv: Sequence[str] | None = None, twin: ControleDoTwin | None = None) -> int:
    p = argparse.ArgumentParser(prog="honeyant-capturar", description=__doc__.splitlines()[0])
    p.add_argument("--duracao", type=float, default=15, help="segundos de tráfego por perfil")
    args = p.parse_args(argv)
    twin = twin or ControleDoTwin()
    try:
        for tipo in TipoDePerfil:
            final = capturar(twin, tipo, DESTINO, args.duracao)
            print(f"{final}: {final.stat().st_size} bytes ({tipo.value})")
        twin.descer()
    except ErroDoTwin as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
