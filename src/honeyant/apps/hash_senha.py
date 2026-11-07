"""Gera o hash da senha do painel.

Uso:
    uv run honeyant-hash-senha
    $env:HONEYANT_PAINEL_SENHA_HASH = '<o hash impresso>'

A senha é pedida sem ecoar (getpass), nunca vem por argumento de linha de comando e nunca
aparece em log. Só o hash é impresso. Guarde-o no `.env` local (está no .gitignore).
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from honeyant.painel.autenticacao import gerar_hash

TAMANHO_MINIMO = 12


def main(
    argv: Sequence[str] | None = None,
    ler: Callable[[str], str] = getpass.getpass,
) -> int:
    argparse.ArgumentParser(
        prog="honeyant-hash-senha",
        description="Pede a senha do painel (sem ecoar) e imprime só o hash.",
    ).parse_args(argv)  # não aceita argumentos: a senha nunca vai na linha de comando

    senha = ler("Senha do painel: ")
    if len(senha) < TAMANHO_MINIMO:
        print(f"A senha precisa ter no mínimo {TAMANHO_MINIMO} caracteres.", file=sys.stderr)
        return 1
    if ler("Repita a senha: ") != senha:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    print(gerar_hash(senha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
