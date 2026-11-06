"""Higiene de texto vindo de fontes hostis (isca)."""

import unicodedata


def limpar(texto: str, limite: int) -> str:
    """Remove caracteres de controle (categoria Unicode Cc) e trunca em `limite`.

    Não escapa HTML: escapar é responsabilidade de quem exibe o texto.
    """
    sem_controles = "".join(c for c in texto if unicodedata.category(c) != "Cc")
    return sem_controles[:limite]
