"""`honeyant-gravar-replay`: grava os replays da demo em `docs/demo/replay-<perfil>.jsonl`.

O replay é o plano B offline do painel: o botão Replay reproduz o formigueiro a
partir desses arquivos, sem rodar o ACO. Usa as mesmas fixtures e o mesmo resumo
do modo local (o real, se houver `resumo-real-*.json`), com a semente 42. Um teste
compara os arquivos versionados com uma geração nova; se ele falhar, rode este
comando de novo e faça commit dos arquivos.
"""

import os
from pathlib import Path

from honeyant.apps.local import ConfigLocal, carregar_fontes
from honeyant.core.casa import TipoDePerfil
from honeyant.pathfinder.adapters.replay import GravadorDeReplay

SEMENTE_DA_DEMO = 42


def _gravadores(demo_dir: Path) -> dict[TipoDePerfil, GravadorDeReplay]:
    fonte, _ = carregar_fontes(demo_dir)
    gravadores = {}
    for perfil in TipoDePerfil:
        gravador = GravadorDeReplay()
        fonte.executar(perfil, SEMENTE_DA_DEMO, [gravador])
        gravadores[perfil] = gravador
    return gravadores


def gerar_replays(demo_dir: Path) -> dict[TipoDePerfil, str]:
    """Conteúdo de cada `.jsonl`, em memória (o teste de regeneração compara com o disco)."""
    return {perfil: g.serializar() for perfil, g in _gravadores(demo_dir).items()}


def main() -> None:
    demo_dir = ConfigLocal.de_ambiente(os.environ).demo_dir
    for perfil, gravador in _gravadores(demo_dir).items():
        destino = gravador.salvar(demo_dir / f"replay-{perfil.value}.jsonl")
        print(f"{destino}: {gravador.total} snapshots")


if __name__ == "__main__":
    main()
