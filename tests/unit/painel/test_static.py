"""O front respeita a CSP e nunca interpreta dado da casa ou da isca como HTML."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeyant.core.casa import PerfilDaCasa, TipoDeNo, TipoDePerfil
from honeyant.painel.app import criar_app

STATIC = Path(__file__).parents[3] / "src" / "honeyant" / "painel" / "static"
DEMO = Path(__file__).parents[3] / "docs" / "demo"
XSS = "<img src=x onerror=alert(1)>"
PROIBIDOS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function",
    "srcdoc",
)
JS = sorted((STATIC / "js").glob("*.js"))


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


def _html_texto() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


def test_html_sem_inline():
    c = _Coletor()
    c.feed(_html_texto())
    assert c.scripts
    assert all(s.get("type") == "module" and s.get("src") for s in c.scripts)
    assert c.atributos_on == []
    assert c.estilos_inline == 0


def test_login_sem_inline_e_com_os_temas_do_painel():
    texto = (STATIC.parent / "login" / "login.html").read_text(encoding="utf-8")
    c = _Coletor()
    c.feed(texto)
    assert c.scripts and all(s.get("src") for s in c.scripts)
    assert c.atributos_on == []
    assert c.estilos_inline == 0
    assert 'href="/static/temas.css"' in texto
    assert 'src="/static/js/tema.js"' in texto


def test_botao_sair_e_formulario_post_sem_js():
    texto = _html_texto()
    assert '<form id="form-sair" class="sair" method="post" action="/logout" hidden>' in texto


def test_arquivos_antigos_removidos():
    assert not (STATIC / "formigueiro.js").exists()
    assert not (STATIC / "formigueiro.css").exists()


@pytest.mark.parametrize("arquivo", JS, ids=lambda p: p.name)
def test_todos_os_js_sem_api_proibida(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    for proibido in PROIBIDOS:
        assert proibido not in texto, f"{arquivo.name} usa {proibido}"


def test_ids_usados_pelo_js_existem():
    html = _html_texto()
    usados = set()
    for arquivo in JS:
        texto = arquivo.read_text("utf-8")
        usados |= set(re.findall(r'(?:getElementById|\$)\("([^"]+)"\)', texto))
    assert usados
    for id_ in usados:
        assert f'id="{id_}"' in html, id_


def test_icones_cobrem_os_tipos():
    svg = (STATIC / "icones.svg").read_text(encoding="utf-8")
    for tipo in TipoDeNo:
        assert f'<symbol id="{tipo.value}"' in svg, tipo.value
    assert '<symbol id="cadeado"' in svg


def test_rotulo_hostil_sai_como_json():
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


@pytest.mark.parametrize(
    "caminho",
    [
        "/static/painel.css",
        "/static/temas.css",
        "/static/icones.svg",
        "/static/layout.json",
        "/static/js/app.js",
    ],
)
def test_estaticos_servidos(caminho):
    class Nada:
        pass

    casas = {
        t: PerfilDaCasa.model_validate_json((DEMO / f"perfil-{t.value}.json").read_text("utf-8"))
        for t in TipoDePerfil
    }
    r = TestClient(criar_app(casas, Nada(), Nada()), base_url="http://127.0.0.1").get(caminho)
    assert r.status_code == 200
