"""A planta do twin: quais dispositivos sobem e em quais tópicos MQTT cada um fala.

Parte das fixtures versionadas em docs/demo/, as mesmas que pathfinder e painel usam.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa, TipoDeNo
from honeyant.twin.planta import (
    TIPOS_DE_DISPOSITIVO,
    PerfilInvalidoParaTwin,
    planejar_dispositivos,
    topico_comando,
    topico_estado,
)

DEMO = Path(__file__).parents[3] / "docs" / "demo"
PERFIS = ["inseguro", "seguro"]


def _perfil(tipo: str) -> PerfilDaCasa:
    texto = (DEMO / f"perfil-{tipo}.json").read_text(encoding="utf-8")
    return PerfilDaCasa.model_validate(json.loads(texto))


def _sem_no(perfil: PerfilDaCasa, id_: str) -> PerfilDaCasa:
    """Perfil sem o nó `id_` e sem as arestas que passavam por ele (continua válido no core)."""
    dados = perfil.model_dump()
    dados["nos"] = [n for n in dados["nos"] if n["id"] != id_]
    dados["arestas"] = [a for a in dados["arestas"] if id_ not in (a["origem"], a["destino"])]
    return PerfilDaCasa.model_validate(dados)


def _sem_aresta(perfil: PerfilDaCasa, chave: str) -> PerfilDaCasa:
    dados = perfil.model_dump()
    dados["arestas"] = [a for a in dados["arestas"] if f"{a['origem']}->{a['destino']}" != chave]
    return PerfilDaCasa.model_validate(dados)


# --- o grafo da casa nos dois perfis versionados ---------------------------------------


@pytest.mark.parametrize("tipo", PERFIS)
def test_planeja_os_5_dispositivos_e_deixa_de_fora_infraestrutura(tipo):
    dispositivos = planejar_dispositivos(_perfil(tipo))

    assert {d.tipo for d in dispositivos} == set(TIPOS_DE_DISPOSITIVO)
    assert len(dispositivos) == 5
    ids = {d.id for d in dispositivos}
    assert not ids & {"internet", "roteador", "broker"}


@pytest.mark.parametrize("tipo", PERFIS)
def test_dispositivos_seguem_a_ordem_do_perfil(tipo):
    ids = [d.id for d in planejar_dispositivos(_perfil(tipo))]

    assert ids == ["camera", "lampada", "tomada", "termostato", "fechadura"]


@pytest.mark.parametrize("tipo", PERFIS)
def test_entrada_e_alvo_do_grafo(tipo):
    p = _perfil(tipo)

    assert p.origem == "internet" and p.no(p.origem).tipo is TipoDeNo.INTERNET
    assert p.alvo == "fechadura" and p.no(p.alvo).tipo is TipoDeNo.FECHADURA


@pytest.mark.parametrize("tipo", PERFIS)
def test_a_rota_da_demonstracao_existe_no_grafo(tipo):
    chaves = {a.chave for a in _perfil(tipo).arestas}

    assert {"internet->camera", "camera->broker", "broker->fechadura"} <= chaves


# --- tópicos MQTT ---------------------------------------------------------------------


def test_cada_dispositivo_tem_topico_proprio_de_estado_e_de_comando():
    camera = next(d for d in planejar_dispositivos(_perfil("inseguro")) if d.id == "camera")

    assert camera.topico_estado == "casa/camera/estado"
    assert camera.topico_comando == "casa/camera/comando"
    assert topico_estado("camera") == camera.topico_estado
    assert topico_comando("camera") == camera.topico_comando


@pytest.mark.parametrize("tipo", PERFIS)
def test_topicos_sao_unicos_e_sem_curinga(tipo):
    dispositivos = planejar_dispositivos(_perfil(tipo))
    topicos = [t for d in dispositivos for t in (d.topico_estado, d.topico_comando)]

    assert len(topicos) == len(set(topicos)) == 10
    for t in topicos:
        assert len(t.split("/")) == 3
        assert "+" not in t and "#" not in t


def test_dispositivo_planejado_e_imutavel():
    dispositivo = planejar_dispositivos(_perfil("inseguro"))[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        dispositivo.topico_comando = "casa/fechadura/comando"  # type: ignore[misc]


# --- perfis que o core aceita mas o twin não consegue subir ----------------------------


@pytest.mark.parametrize("id_", ["camera", "lampada", "tomada", "termostato"])
def test_recusa_perfil_sem_um_dos_dispositivos(id_):
    perfil = _sem_no(_perfil("inseguro"), id_)

    with pytest.raises(PerfilInvalidoParaTwin, match=f"faltam.*{id_}"):
        planejar_dispositivos(perfil)


def test_recusa_dispositivo_duplicado():
    dados = _perfil("inseguro").model_dump()
    dados["nos"].append(
        {
            "id": "camera2",
            "tipo": TipoDeNo.CAMERA,
            "rotulo": "Câmera 2",
            "x": 0,
            "y": 0,
            "sensibilidade": 1,
        }
    )

    with pytest.raises(PerfilInvalidoParaTwin, match="mais de um.*camera"):
        planejar_dispositivos(PerfilDaCasa.model_validate(dados))


def test_recusa_perfil_sem_broker():
    perfil = _sem_no(_perfil("inseguro"), "broker")

    with pytest.raises(PerfilInvalidoParaTwin, match="broker"):
        planejar_dispositivos(perfil)


def test_recusa_dispositivo_sem_ligacao_com_o_broker():
    perfil = _sem_aresta(_perfil("inseguro"), "lampada->broker")

    with pytest.raises(PerfilInvalidoParaTwin, match="sem ligação.*lampada"):
        planejar_dispositivos(perfil)
