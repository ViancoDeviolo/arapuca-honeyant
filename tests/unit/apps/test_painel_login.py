"""`encaixe_do_ambiente`: sem hash o painel abre como hoje; hash inválido impede de subir."""

import pytest

from honeyant.apps.painel_login import encaixe_do_ambiente
from honeyant.painel.autenticacao import gerar_hash

HASH = gerar_hash("senha-de-teste-123")


def test_sem_a_variavel_o_encaixe_vem_vazio():
    encaixe = encaixe_do_ambiente({})
    assert not encaixe.protecao_api and not encaixe.protecao_pagina and not encaixe.routers


@pytest.mark.parametrize(
    "valor", ["", "texto-qualquer", "bcrypt$16384$8$1$AAAA$AAAA", "scrypt$16384$8$1$AAAA"]
)
def test_hash_invalido_levanta_value_error_sem_repetir_o_valor(valor):
    with pytest.raises(ValueError, match="honeyant-hash-senha") as erro:
        encaixe_do_ambiente({"HONEYANT_PAINEL_SENHA_HASH": valor})
    if valor:
        assert valor not in str(erro.value)


def test_hash_valido_monta_protecoes_e_router():
    encaixe = encaixe_do_ambiente({"HONEYANT_PAINEL_SENHA_HASH": HASH})
    assert len(encaixe.protecao_api) == 1
    assert len(encaixe.protecao_pagina) == 1
    assert len(encaixe.routers) == 1


@pytest.mark.parametrize(("valor", "secure"), [("1", True), ("0", False), (None, True)])
def test_cookie_seguro_por_variavel_com_padrao_1(valor, secure):
    env = {"HONEYANT_PAINEL_SENHA_HASH": HASH}
    if valor is not None:
        env["HONEYANT_PAINEL_COOKIE_SEGURO"] = valor
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    for router in encaixe_do_ambiente(env).routers:
        app.include_router(router)
    r = TestClient(app, base_url="https://127.0.0.1", follow_redirects=False).post(
        "/login",
        content="senha=senha-de-teste-123",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert ("secure" in r.headers["set-cookie"].lower()) is secure


def test_valor_estranho_em_cookie_seguro_nao_sobe():
    with pytest.raises(ValueError, match="HONEYANT_PAINEL_COOKIE_SEGURO"):
        encaixe_do_ambiente(
            {"HONEYANT_PAINEL_SENHA_HASH": HASH, "HONEYANT_PAINEL_COOKIE_SEGURO": "talvez"}
        )
