"""Recusa no próprio PC o que foi colado no lugar da chave de acesso.

Cada chave errada que chega ao resumo-api gasta uma das 5 tentativas do IP (e a quinta
bloqueia por 15 min). O rótulo, o hash e as aspas nunca fazem parte da chave, então nem
saem do PC.
"""

import re

_REPITA = "Cole de novo só a chave: a linha de baixo de “Chave de acesso”."
_ESPACO_OU_ASPAS = re.compile(r"[\s'\"“”‘’`´]")


def problema_na_chave(texto: str) -> str | None:
    """O motivo para recusar o texto colado, ou None se ele pode ser uma chave."""
    if texto.startswith("Chave de acesso"):
        return f"Você colou o rótulo junto. {_REPITA}"
    if texto.startswith(("HONEYANT_", "scrypt")):
        return f"Isso é o hash que vai para a EC2, não a chave. {_REPITA}"
    if _ESPACO_OU_ASPAS.search(texto):
        return f"A chave não tem espaços nem aspas (aspas curvas do WhatsApp?). {_REPITA}"
    return None
