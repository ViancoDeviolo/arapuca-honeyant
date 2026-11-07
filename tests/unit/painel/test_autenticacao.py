"""Hash, bloqueio por tentativas, sessões e dependências de proteção (sem rede, sem sleep)."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from honeyant.painel.autenticacao import (
    COOKIE,
    LimiteDeTentativas,
    Sessoes,
    criar_protecoes,
    gerar_hash,
    hash_valido,
    verificar_senha,
)

SENHA = "senha-de-teste-123"  # noqa: S105  (valor falso, só para os testes)
IP = "127.0.0.1"


class RelogioFalso:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


# --- 3.1 hash ----------------------------------------------------------------------


def test_hash_no_formato_combinado_e_sem_a_senha():
    h = gerar_hash(SENHA)
    assert h.startswith("scrypt$16384$8$1$")
    assert len(h.split("$")) == 6
    assert SENHA not in h


def test_senha_certa_aceita_e_errada_recusada():
    h = gerar_hash(SENHA)
    assert verificar_senha(SENHA, h) is True
    assert verificar_senha(SENHA + "x", h) is False
    assert verificar_senha("", h) is False


def test_dois_hashes_da_mesma_senha_sao_diferentes_por_causa_do_sal():
    assert gerar_hash(SENHA) != gerar_hash(SENHA)


def test_sal_fixo_gera_hash_reproduzivel():
    sal = b"\x01" * 16
    assert gerar_hash(SENHA, sal=sal) == gerar_hash(SENHA, sal=sal)


def test_senha_com_acentos_e_emoji():
    assert verificar_senha("sênha-çom-🐜-123", gerar_hash("sênha-çom-🐜-123")) is True


@pytest.mark.parametrize(
    "malformado",
    [
        "",
        "texto qualquer",
        "scrypt$16384$8$1$AAAA",  # faltam campos
        "scrypt$abc$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "scrypt$16385$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "scrypt$4294967296$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "scrypt$262144$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "scrypt$16384$8$1$@@@@$@@@@",  # base64 inválido
        "bcrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ],
)
def test_hash_malformado_ou_com_n_gigante_da_false_sem_levantar(malformado):
    assert hash_valido(malformado) is False
    assert verificar_senha(SENHA, malformado) is False


def test_hash_gerado_e_valido():
    assert hash_valido(gerar_hash(SENHA)) is True


def test_senha_gigante_e_recusada_sem_calcular():
    assert verificar_senha("a" * 100_000, gerar_hash(SENHA)) is False


# --- 3.2 limite de tentativas ------------------------------------------------------


def test_quatro_falhas_nao_bloqueiam_e_a_quinta_bloqueia():
    lim = LimiteDeTentativas(relogio=RelogioFalso())
    for _ in range(4):
        lim.falhou(IP)
    assert lim.bloqueado(IP) == 0
    lim.falhou(IP)
    assert lim.bloqueado(IP) == 900


def test_bloqueio_passa_depois_de_900_segundos():
    relogio = RelogioFalso()
    lim = LimiteDeTentativas(relogio=relogio)
    for _ in range(5):
        lim.falhou(IP)
    relogio.avancar(899)
    assert lim.bloqueado(IP) == 1
    relogio.avancar(1)
    assert lim.bloqueado(IP) == 0


def test_acerto_zera_o_contador():
    lim = LimiteDeTentativas(relogio=RelogioFalso())
    for _ in range(4):
        lim.falhou(IP)
    lim.acertou(IP)
    lim.falhou(IP)
    assert lim.bloqueado(IP) == 0


def test_um_ip_nao_afeta_outro():
    lim = LimiteDeTentativas(relogio=RelogioFalso())
    for _ in range(5):
        lim.falhou(IP)
    assert lim.bloqueado("198.51.100.7") == 0


def test_falhas_fora_da_janela_nao_acumulam():
    relogio = RelogioFalso()
    lim = LimiteDeTentativas(relogio=relogio)
    for _ in range(4):
        lim.falhou(IP)
    relogio.avancar(901)
    lim.falhou(IP)
    assert lim.bloqueado(IP) == 0


def test_teto_de_ips_descarta_os_mais_antigos():
    lim = LimiteDeTentativas(relogio=RelogioFalso(), teto_de_ips=3)
    for i in range(10):
        lim.falhou(f"203.0.113.{i}")
    assert lim.tamanho == 3


# --- 3.3 sessões -------------------------------------------------------------------


def test_token_criado_e_valido_e_inventado_nao():
    sessoes = Sessoes(relogio=RelogioFalso())
    token = sessoes.criar()
    assert len(token) >= 43
    assert sessoes.valida(token) is True
    assert sessoes.valida("inventado") is False


@pytest.mark.parametrize("token", [None, "", "x" * 5000, "ação"])
def test_token_ausente_ou_estranho_nao_valida(token):
    assert Sessoes(relogio=RelogioFalso()).valida(token) is False


def test_token_expira_depois_da_validade():
    relogio = RelogioFalso()
    sessoes = Sessoes(relogio=relogio)
    token = sessoes.criar()
    relogio.avancar(8 * 3600 - 1)
    assert sessoes.valida(token) is True
    relogio.avancar(1)
    assert sessoes.valida(token) is False
    assert sessoes.tamanho == 0  # a sessão vencida foi apagada


def test_token_encerrado_deixa_de_valer():
    sessoes = Sessoes(relogio=RelogioFalso())
    token = sessoes.criar()
    sessoes.encerrar(token)
    assert sessoes.valida(token) is False


def test_servidor_nao_guarda_o_token_em_claro_e_tokens_sao_distintos():
    sessoes = Sessoes(relogio=RelogioFalso())
    t1, t2 = sessoes.criar(), sessoes.criar()
    assert t1 != t2
    assert t1 not in repr(sessoes.__dict__)


def test_teto_de_sessoes():
    sessoes = Sessoes(relogio=RelogioFalso(), teto=2)
    primeiro = sessoes.criar()
    sessoes.criar()
    sessoes.criar()
    assert sessoes.valida(primeiro) is False and sessoes.tamanho == 2


# --- 3.4 dependências de proteção --------------------------------------------------


@pytest.fixture
def sessoes() -> Sessoes:
    return Sessoes(relogio=RelogioFalso())


def _app(sessoes: Sessoes) -> TestClient:
    api, pagina = criar_protecoes(sessoes)
    app = FastAPI()

    @app.get("/api/x", dependencies=[api])
    def rota_api() -> dict:
        return {"ok": True}

    @app.get("/pagina", dependencies=[pagina])
    def rota_pagina() -> dict:
        return {"ok": True}

    return TestClient(app, follow_redirects=False)


def test_protecao_da_api_da_401_sem_sessao(sessoes):
    assert _app(sessoes).get("/api/x").status_code == 401


def test_protecao_da_pagina_redireciona_para_o_login(sessoes):
    r = _app(sessoes).get("/pagina")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_cookie_inventado_nao_entra(sessoes):
    cliente = _app(sessoes)
    cliente.cookies.set(COOKIE, "inventado")
    assert cliente.get("/api/x").status_code == 401
    assert cliente.get("/pagina").status_code == 303


def test_sessao_valida_libera_api_e_pagina(sessoes):
    cliente = _app(sessoes)
    cliente.cookies.set(COOKIE, sessoes.criar())
    assert cliente.get("/api/x").status_code == 200
    assert cliente.get("/pagina").status_code == 200


def test_protecoes_levantam_http_exception_no_formato_do_encaixe(sessoes):
    import asyncio

    from starlette.requests import Request

    api, pagina = criar_protecoes(sessoes)
    pedido = Request({"type": "http", "headers": [], "query_string": b"", "path": "/"})
    with pytest.raises(HTTPException) as erro_api:
        asyncio.run(api.dependency(pedido))
    with pytest.raises(HTTPException) as erro_pagina:
        asyncio.run(pagina.dependency(pedido))
    assert erro_api.value.status_code == 401
    assert erro_pagina.value.status_code == 303
    assert erro_pagina.value.headers == {"Location": "/login"}
