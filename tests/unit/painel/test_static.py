"""O front respeita a CSP e nunca interpreta dado da casa ou da isca como HTML."""

import re
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.painel.app import criar_app

STATIC = Path(__file__).parents[3] / "src" / "honeyant" / "painel" / "static"
DEMO = Path(__file__).parents[3] / "docs" / "demo"
XSS = "<img src=x onerror=alert(1)>"


class _Coletor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[dict] = []
        self.atributos_on: list[str] = []
        self.estilos_inline = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.scripts.append(a)
        if tag == "style":
            self.estilos_inline += 1
        self.atributos_on += [n for n in a if n.startswith("on")]
        if "style" in a:
            self.estilos_inline += 1


def _html() -> _Coletor:
    c = _Coletor()
    c.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    return c


def test_html_sem_script_nem_estilo_inline():
    c = _html()
    assert c.scripts and all(s.get("src") for s in c.scripts)
    assert c.atributos_on == []
    assert c.estilos_inline == 0


def test_html_tem_os_elementos_que_o_js_usa():
    texto = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "formigueiro.js").read_text(encoding="utf-8")
    for id_ in re.findall(r'getElementById\("([^"]+)"\)', js):
        assert f'id="{id_}"' in texto, id_


def test_js_nunca_usa_innerHTML_nem_eval():
    js = (STATIC / "formigueiro.js").read_text(encoding="utf-8")
    for proibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function"):
        assert proibido not in js


def test_rotulo_com_html_sai_como_json_intacto():
    dados = PerfilDaCasa.model_validate_json(
        (DEMO / "perfil-inseguro.json").read_text("utf-8")
    ).model_dump()
    dados["nos"][1]["rotulo"] = XSS
    perfil = PerfilDaCasa.model_validate(dados)

    class SemSnapshots:
        def snapshots(self, perfil, semente):
            return []

    casas = {TipoDePerfil.INSEGURO: perfil, TipoDePerfil.SEGURO: perfil}
    app = criar_app(casas, SemSnapshots(), None)
    r = TestClient(app, base_url="http://127.0.0.1").get("/api/v1/casa")
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["nos"][1]["rotulo"] == XSS
