"""`honeyant-mitigar`: aplica (ou desfaz) a mitigação real na casa simulada.

    uv run honeyant-mitigar              # inseguro -> seguro
    uv run honeyant-mitigar --desfazer   # seguro -> inseguro (para repetir a demo)

Padrão Command: cada ação é um objeto com `executar()`, e o `main` só escolhe qual rodar.
A mitigação é a troca de perfil do spec-mãe (seção 10): credencial forte por dispositivo,
TLS na 8883, autenticação + ACL por tópico e câmera numa rede separada. O broker e os
dispositivos são recriados. O botão do painel continua só visual e aponta para as capturas.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from honeyant.apps.twin import ControleDoTwin, ErroDoTwin
from honeyant.core.casa import TipoDePerfil


class Comando(Protocol):
    descricao: str

    def executar(self) -> None: ...


@dataclass
class TrocarPerfil:
    """Derruba a casa e sobe de novo no perfil `destino` (com as configs já preparadas)."""

    twin: ControleDoTwin
    destino: TipoDePerfil
    descricao: str

    def executar(self) -> None:
        self.twin.descer()
        self.twin.subir(self.destino)


def aplicar(twin: ControleDoTwin) -> Comando:
    return TrocarPerfil(
        twin,
        TipoDePerfil.SEGURO,
        "mitigação aplicada: TLS na 8883, senha forte por dispositivo, ACL por tópico "
        "e câmera isolada",
    )


def desfazer(twin: ControleDoTwin) -> Comando:
    return TrocarPerfil(
        twin,
        TipoDePerfil.INSEGURO,
        "mitigação desfeita: de volta à 1883 sem TLS, sem senha e sem ACL",
    )


def main(argv: Sequence[str] | None = None, twin: ControleDoTwin | None = None) -> int:
    p = argparse.ArgumentParser(prog="honeyant-mitigar", description=__doc__.splitlines()[0])
    p.add_argument("--desfazer", action="store_true", help="volta ao perfil inseguro")
    args = p.parse_args(argv)
    twin = twin or ControleDoTwin()
    comando = (desfazer if args.desfazer else aplicar)(twin)
    try:
        comando.executar()
    except ErroDoTwin as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    print(comando.descricao)
    return 0


if __name__ == "__main__":
    sys.exit(main())
