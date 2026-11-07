"""Credenciais conhecidas = completas do resumo ∪ padrões de fábrica de IoT."""

import json
from pathlib import Path

from honeyant.core.credenciais import (
    CREDENCIAIS_PADRAO_DE_FABRICA,
    CREDENCIAL_DA_CAMERA,
    credenciais_completas,
    credenciais_conhecidas,
)
from honeyant.core.resumo import ResumoDeAmeaca

DEMO = Path(__file__).parents[3] / "docs" / "demo"


def _resumo(top):
    dados = json.loads((DEMO / "resumo-congelado.json").read_text("utf-8"))
    dados["top_credenciais"] = top
    return ResumoDeAmeaca.model_validate(dados)


def test_camera_usa_uma_credencial_padrao_de_fabrica():
    assert CREDENCIAL_DA_CAMERA in CREDENCIAIS_PADRAO_DE_FABRICA
    assert CREDENCIAL_DA_CAMERA in credenciais_conhecidas()


def test_so_entram_credenciais_completas():
    resumo = _resumo(
        [
            {"usuario": "", "senha": None, "tentativas": 1},
            {"usuario": "MGLNDD_<ipv4>_23", "senha": None, "tentativas": 1},
            {"usuario": "root", "senha": "", "tentativas": 1},
            {"usuario": "root", "senha": "xc3511", "tentativas": 9},
        ]
    )
    assert credenciais_completas(resumo) == {("root", "xc3511")}


def test_uniao_com_os_padroes_de_fabrica():
    resumo = _resumo([{"usuario": "root", "senha": "xc3511", "tentativas": 9}])
    conhecidas = credenciais_conhecidas(resumo)
    assert ("root", "xc3511") in conhecidas
    assert CREDENCIAIS_PADRAO_DE_FABRICA <= conhecidas


def test_resumo_sem_credencial_completa_ainda_conhece_os_padroes():
    resumo = _resumo([{"usuario": "", "senha": None, "tentativas": 1}])
    assert credenciais_conhecidas(resumo) == CREDENCIAIS_PADRAO_DE_FABRICA
