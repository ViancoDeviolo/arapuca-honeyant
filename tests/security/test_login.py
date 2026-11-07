"""Login do painel: proteção das rotas, cookie, bloqueio, CSRF de login, limite do corpo e logs.

Monta um app de teste igual ao que a fábrica do Lucas monta com o `Encaixe`: o router do login
sem proteção, e as rotas `/api/v1/*` e `/` com as proteções. Base `https://127.0.0.1` porque o
cookie é `Secure` e o cliente de teste só o reenvia por https.
"""

import logging
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from honeyant.painel.autenticacao import (
    COOKIE,
    LimiteDeTentativas,
    Sessoes,
    criar_protecoes,
    criar_router_login,
    gerar_hash,
)

LOGIN = Path(__file__).parents[2] / "src" / "honeyant" / "painel" / "login"
SENHA = "senha-de-teste-123"  # noqa: S105  (valor falso, só para os testes)
BASE = "https://127.0.0.1"
FORM = {"Content-Type": "application/x-www-form-urlencoded"}


class RelogioFalso:
    agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture(scope="module")
def hash_da_senha() -> str:
    return gerar_hash(SENHA)


@pytest.fixture
def cliente(hash_da_senha) -> TestClient:
    relogio = RelogioFalso()
    sessoes, limite = Sessoes(relogio=relogio), LimiteDeTentativas(relogio=relogio)
    api, pagina = criar_protecoes(sessoes)
    app = FastAPI()
    app.include_router(criar_router_login(hash_da_senha, sessoes, limite))
    protegido_api = APIRouter(dependencies=[api])
    protegido_pagina = APIRouter(dependencies=[pagina])

    @protegido_api.get("/api/v1/perfil")
    def perfil() -> dict:
        return {"ok": True}

    @protegido_api.get("/api/v1/formigueiro/stream")
    def stream() -> PlainTextResponse:
        return PlainTextResponse("event: fim\ndata: {}\n\n", media_type="text/event-stream")

    @protegido_pagina.get("/")
    def inicio() -> PlainTextResponse:
        return PlainTextResponse("painel")

    app.include_router(protegido_api)
    app.include_router(protegido_pagina)
    return TestClient(app, base_url=BASE, follow_redirects=False)


def _entrar(cliente, senha=SENHA, origem=None, corpo=None):
    cabecalhos = dict(FORM)
    if origem:
        cabecalhos["Origin"] = origem
    return cliente.post(
        "/login", content=corpo if corpo is not None else f"senha={senha}", headers=cabecalhos
    )


# 1. sem login ------------------------------------------------------------------------


@pytest.mark.parametrize("caminho", ["/api/v1/perfil", "/api/v1/formigueiro/stream"])
def test_api_e_stream_sem_login_dao_401(cliente, caminho):
    assert cliente.get(caminho).status_code == 401


def test_pagina_sem_login_da_303_para_o_login(cliente):
    r = cliente.get("/")
    assert r.status_code == 303 and r.headers["location"] == "/login"


@pytest.mark.parametrize("caminho", ["/login", "/login/login.css", "/login/login.js"])
def test_arquivos_do_login_sao_publicos(cliente, caminho):
    assert cliente.get(caminho).status_code == 200


# 2. senha certa ----------------------------------------------------------------------


def test_senha_certa_da_cookie_com_flags_e_libera_api_e_stream(cliente):
    r = _entrar(cliente)
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/", "max-age=28800"):
        assert flag in cookie
    assert cliente.get("/api/v1/perfil").status_code == 200
    assert cliente.get("/api/v1/formigueiro/stream").status_code == 200
    assert cliente.get("/").status_code == 200


def test_cookie_seguro_pode_ser_desligado_so_por_parametro(hash_da_senha):
    relogio = RelogioFalso()
    app = FastAPI()
    app.include_router(
        criar_router_login(
            hash_da_senha,
            Sessoes(relogio=relogio),
            LimiteDeTentativas(relogio=relogio),
            cookie_seguro=False,
        )
    )
    r = TestClient(app, base_url="http://127.0.0.1", follow_redirects=False).post(
        "/login", content=f"senha={SENHA}", headers=FORM
    )
    assert "secure" not in r.headers["set-cookie"].lower()


def test_senha_errada_volta_para_o_login_com_erro_e_sem_cookie(cliente):
    r = _entrar(cliente, senha="errada")
    assert r.status_code == 303 and r.headers["location"] == "/login?erro=1"
    assert "set-cookie" not in r.headers


# 3. bloqueio -------------------------------------------------------------------------


def test_sexta_tentativa_da_429_mesmo_com_a_senha_certa(cliente):
    for _ in range(5):
        assert _entrar(cliente, senha="errada").status_code == 303
    r = _entrar(cliente)
    assert r.status_code == 429
    assert "15 min" in r.text and "set-cookie" not in r.headers


# 4. CSRF de login --------------------------------------------------------------------


@pytest.mark.parametrize("origem", ["http://evil.com", "https://127.0.0.1.evil.com", "null"])
def test_origin_de_outro_site_da_403(cliente, origem):
    r = _entrar(cliente, origem=origem)
    assert r.status_code == 403 and "set-cookie" not in r.headers


@pytest.mark.parametrize(
    "origem", ["http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"]
)
def test_origin_do_proprio_painel_passa_ignorando_a_porta(cliente, origem):
    assert _entrar(cliente, origem=origem).status_code == 303


# 5. corpo grande ---------------------------------------------------------------------


def test_corpo_acima_de_4kb_da_413(cliente):
    assert _entrar(cliente, corpo="senha=" + "a" * 5000).status_code == 413


def test_campo_senha_ausente_conta_como_senha_errada(cliente):
    r = _entrar(cliente, corpo="outro=1")
    assert r.status_code == 303 and r.headers["location"] == "/login?erro=1"


# 6 e 7. cookie inventado e logout ----------------------------------------------------


def test_cookie_inventado_da_401(cliente):
    cliente.cookies.set(COOKIE, "inventado")
    assert cliente.get("/api/v1/perfil").status_code == 401


def test_logout_invalida_o_mesmo_cookie(cliente):
    _entrar(cliente)
    token = cliente.cookies.get(COOKIE)
    r = cliente.post("/logout")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert "max-age=0" in r.headers["set-cookie"].lower()
    cliente.cookies.clear()
    cliente.cookies.set(COOKIE, token)
    assert cliente.get("/api/v1/perfil").status_code == 401


def test_logout_de_outro_origin_da_403_e_a_sessao_continua(cliente):
    _entrar(cliente)
    assert cliente.post("/logout", headers={"Origin": "http://evil.com"}).status_code == 403
    assert cliente.get("/api/v1/perfil").status_code == 200


def test_logout_por_get_nao_existe(cliente):
    assert cliente.get("/logout").status_code in (404, 405)


# 8. logs -----------------------------------------------------------------------------


def test_senha_token_e_hash_nunca_aparecem_nos_logs(cliente, hash_da_senha, caplog):
    caplog.set_level(logging.DEBUG)
    _entrar(cliente, senha="errada-secreta-abc")
    for _ in range(5):
        _entrar(cliente, senha="outra-errada-xyz")
    texto = caplog.text
    assert "errada-secreta-abc" not in texto and "outra-errada-xyz" not in texto
    assert hash_da_senha not in texto and "scrypt$" not in texto


def test_token_da_sessao_nao_aparece_nos_logs(cliente, caplog):
    caplog.set_level(logging.DEBUG)
    _entrar(cliente)
    token = cliente.cookies.get(COOKIE)
    cliente.get("/api/v1/perfil")
    cliente.post("/logout")
    assert token and token not in caplog.text


# tela de login -----------------------------------------------------------------------


class _Coletor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[dict] = []
        self.atributos_on: list[str] = []
        self.estilos_inline = 0
        self.campos: list[dict] = []
        self.labels = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.scripts.append(a)
        if tag == "style" or "style" in a:
            self.estilos_inline += 1
        if tag == "input":
            self.campos.append(a)
        if tag == "label":
            self.labels += 1
        self.atributos_on += [n for n in a if n.startswith("on")]


def test_tela_sem_script_nem_estilo_inline_e_com_campo_unico_de_senha():
    c = _Coletor()
    c.feed((LOGIN / "login.html").read_text(encoding="utf-8"))
    assert c.scripts and all(s.get("src") for s in c.scripts)
    assert c.atributos_on == [] and c.estilos_inline == 0
    assert len(c.campos) == 1
    campo = c.campos[0]
    assert campo["name"] == "senha" and campo["type"] == "password"
    assert campo["autocomplete"] == "current-password"
    assert c.labels >= 1
    html = (LOGIN / "login.html").read_text(encoding="utf-8")
    assert 'method="post"' in html and 'action="/login"' in html


def test_html_tem_os_elementos_que_o_js_usa():
    html = (LOGIN / "login.html").read_text(encoding="utf-8")
    js = (LOGIN / "login.js").read_text(encoding="utf-8")
    for id_ in re.findall(r'getElementById\("([^"]+)"\)', js):
        assert f'id="{id_}"' in html, id_


def test_js_usa_textcontent_e_nunca_apis_perigosas():
    js = (LOGIN / "login.js").read_text(encoding="utf-8")
    assert "textContent" in js and "location.search" in js
    for proibido in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
    ):
        assert proibido not in js


def test_css_mostra_foco_visivel():
    css = (LOGIN / "login.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css and "outline" in css
