"""O modo local liga o login do Gustavo quando há hash no ambiente.

Estes testes montam o app pelo mesmo caminho do `main()`. Se alguém voltar a montar o
painel com o `Encaixe()` vazio, eles falham: é o que impede o login de ser desligado
sem ninguém notar.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeyant.apps import local
from honeyant.painel.autenticacao import gerar_hash

DEMO = Path(__file__).parents[3] / "docs" / "demo"
SENHA = "senha-de-teste-123"
BASE = "http://127.0.0.1"


def _env(**extra: str) -> dict[str, str]:
    return {"HONEYANT_DEMO_DIR": str(DEMO), **extra}


@pytest.fixture(scope="module")
def hash_teste() -> str:
    return gerar_hash(SENHA)


def _cliente_do_main(monkeypatch, env: dict[str, str]) -> TestClient:
    """Roda o `main()` de verdade, trocando só o servidor web por um que guarda o app."""
    capturado = {}

    def falso_run(app, host, port):
        capturado.update(app=app, host=host, port=port)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", falso_run)
    for chave in ("HONEYANT_PAINEL_SENHA_HASH", "HONEYANT_PAINEL_COOKIE_SEGURO"):
        monkeypatch.delenv(chave, raising=False)
    for chave, valor in env.items():
        monkeypatch.setenv(chave, valor)
    local.main()
    assert capturado["host"] == "127.0.0.1"
    return TestClient(capturado["app"], base_url=BASE)


def test_com_hash_a_api_exige_sessao(monkeypatch, hash_teste):
    c = _cliente_do_main(monkeypatch, _env(HONEYANT_PAINEL_SENHA_HASH=hash_teste))
    assert c.get("/api/v1/casa?perfil=inseguro").status_code == 401
    assert c.get("/api/v1/sessao").status_code == 401


def test_com_hash_a_pagina_redireciona_para_o_login(monkeypatch, hash_teste):
    c = _cliente_do_main(monkeypatch, _env(HONEYANT_PAINEL_SENHA_HASH=hash_teste))
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert c.get("/login").status_code == 200


def test_com_hash_entrar_libera_a_api_e_sair_encerra(monkeypatch, hash_teste):
    env = _env(HONEYANT_PAINEL_SENHA_HASH=hash_teste, HONEYANT_PAINEL_COOKIE_SEGURO="0")
    c = _cliente_do_main(monkeypatch, env)
    origem = {"Origin": BASE}
    r = c.post("/login", data={"senha": SENHA}, headers=origem, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert c.get("/api/v1/sessao").json() == {"login": True}
    assert c.get("/api/v1/casa?perfil=inseguro").status_code == 200

    r = c.post("/logout", headers=origem, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert c.get("/api/v1/casa?perfil=inseguro").status_code == 401


def test_sem_hash_o_painel_abre_e_avisa_que_nao_ha_login(monkeypatch):
    c = _cliente_do_main(monkeypatch, _env())
    assert c.get("/").status_code == 200
    assert c.get("/api/v1/sessao").json() == {"login": False}
    assert c.get("/login").status_code == 404


def test_hash_invalido_impede_de_subir(monkeypatch):
    with pytest.raises(ValueError, match="honeyant-hash-senha"):
        _cliente_do_main(monkeypatch, _env(HONEYANT_PAINEL_SENHA_HASH="nao-e-hash"))
