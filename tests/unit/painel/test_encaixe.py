"""Ponto de encaixe do login (spec, seção 3.5) e proteção contra DNS rebinding (3.9)."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, HTTPException
from fastapi.testclient import TestClient

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.painel.app import Encaixe, criar_app

DEMO = Path(__file__).parents[3] / "docs" / "demo"
LOCAL = "http://127.0.0.1"


def _casas() -> dict[TipoDePerfil, PerfilDaCasa]:
    return {
        t: PerfilDaCasa.model_validate_json((DEMO / f"perfil-{t.value}.json").read_text("utf-8"))
        for t in TipoDePerfil
    }


class SemSnapshots:
    def snapshots(self, perfil, semente):
        return []

    def replay(self, perfil):
        return None

    def analise(self, perfil):
        raise AssertionError("não usado")


class SemResumo:
    def resumo(self):
        raise AssertionError("não usado")


def recusa_api() -> None:
    raise HTTPException(401)


def recusa_pagina() -> None:
    raise HTTPException(303, headers={"Location": "/login"})


ENCAIXE = Encaixe(protecao_api=[Depends(recusa_api)], protecao_pagina=[Depends(recusa_pagina)])


def _app(**kwargs):
    return criar_app(_casas(), SemSnapshots(), SemResumo(), **kwargs)


@pytest.mark.parametrize(
    "rota",
    [
        "/api/v1/casa",
        "/api/v1/rotas",
        "/api/v1/resumo",
        "/api/v1/replay",
        "/api/v1/formigueiro/stream",
    ],
)
def test_protecao_da_api_responde_401(rota):
    c = TestClient(_app(encaixe=ENCAIXE), base_url=LOCAL)
    assert c.get(rota).status_code == 401


def test_protecao_da_pagina_redireciona_para_o_login():
    c = TestClient(_app(encaixe=ENCAIXE), base_url=LOCAL, follow_redirects=False)
    r = c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_routers_do_encaixe_ficam_fora_da_protecao():
    extra = APIRouter()
    extra.get("/login")(lambda: {"ok": True})
    enc = Encaixe(ENCAIXE.protecao_api, ENCAIXE.protecao_pagina, routers=[extra])
    c = TestClient(_app(encaixe=enc), base_url=LOCAL)
    assert c.get("/login").status_code == 200


def test_sem_encaixe_tudo_abre():
    c = TestClient(_app(), base_url=LOCAL)
    assert c.get("/").status_code == 200
    assert c.get("/api/v1/casa").status_code == 200


def test_host_desconhecido_recebe_400():
    c = TestClient(_app(), base_url=LOCAL)
    assert c.get("/api/v1/casa", headers={"Host": "evil.com"}).status_code == 400


def test_localhost_e_aceito():
    assert TestClient(_app(), base_url="http://localhost").get("/").status_code == 200


def test_hosts_permitidos_vem_por_parametro():
    c = TestClient(_app(hosts_permitidos=["painel.exemplo"]), base_url="http://painel.exemplo")
    assert c.get("/").status_code == 200
    assert c.get("/", headers={"Host": "127.0.0.1"}).status_code == 400
