"""Composition root do login do painel: lê o ambiente e monta o `Encaixe` da fábrica do app.

Variáveis:
    HONEYANT_PAINEL_SENHA_HASH     hash gerado por `honeyant-hash-senha` (nunca a senha)
    HONEYANT_PAINEL_COOKIE_SEGURO  1 (padrão) ou 0; só para um navegador que recuse o cookie
                                   `Secure` em http://127.0.0.1

Sem a primeira, o painel abre sem login, como hoje (e continua preso ao loopback pelo
`ConfigLocal`). Com um hash inválido, levanta `ValueError` e o painel não sobe.
"""

import os
from collections.abc import Mapping

from honeyant.painel.app import Encaixe
from honeyant.painel.autenticacao import (
    LimiteDeTentativas,
    Sessoes,
    criar_protecoes,
    criar_router_login,
    hash_valido,
)


def _cookie_seguro(env: Mapping[str, str]) -> bool:
    valor = env.get("HONEYANT_PAINEL_COOKIE_SEGURO", "1").strip()
    if valor not in {"0", "1"}:
        raise ValueError("HONEYANT_PAINEL_COOKIE_SEGURO deve ser 1 ou 0")
    return valor == "1"


def encaixe_do_ambiente(env: Mapping[str, str] = os.environ) -> Encaixe:
    hash_salvo = env.get("HONEYANT_PAINEL_SENHA_HASH")
    if hash_salvo is None:
        return Encaixe()
    hash_salvo = hash_salvo.strip()
    if not hash_valido(hash_salvo):
        # Nunca repete o valor: ele é segredo.
        raise ValueError(
            "HONEYANT_PAINEL_SENHA_HASH não é um hash scrypt válido "
            "(gere com `uv run honeyant-hash-senha`)"
        )
    sessoes, limite = Sessoes(), LimiteDeTentativas()
    api, pagina = criar_protecoes(sessoes)
    router = criar_router_login(hash_salvo, sessoes, limite, cookie_seguro=_cookie_seguro(env))
    return Encaixe(protecao_api=[api], protecao_pagina=[pagina], routers=[router])
