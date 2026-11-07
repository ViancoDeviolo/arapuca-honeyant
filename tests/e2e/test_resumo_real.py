"""Trava da demo com o resumo real da isca (docs/demo/resumo-real-AAAA-MM-DD.json).

Só roda quando o arquivo existe (ele é gerado na EC2 com `honeyant-exportar-resumo`).
Se `test_rotas_da_demo_com_o_resumo_real` falhar, NÃO calibre fixture nenhuma: avise o
Lucas antes (spec do painel, 3.7). Depois de trocar o resumo, regenere os replays com
`uv run honeyant-gravar-replay`.

O resumo real não precisa ter credencial completa (o de 07/11 não tinha nenhuma): a câmera
usa uma credencial padrão de fábrica, conhecida pelas listas públicas (core/credenciais.py).
"""

import re
from pathlib import Path

import pytest

from honeyant.apps.local import carregar_fontes
from honeyant.core.casa import TipoDePerfil
from honeyant.core.credenciais import (
    CREDENCIAL_DA_CAMERA,
    credenciais_completas,
    credenciais_conhecidas,
)
from honeyant.core.resumo import ResumoDeAmeaca

DEMO = Path(__file__).parents[2] / "docs" / "demo"
REAIS = sorted(DEMO.glob("resumo-real-*.json"))
QUALQUER_IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")

pytestmark = pytest.mark.skipif(not REAIS, reason="sem resumo real em docs/demo")


@pytest.fixture(scope="module")
def resumo() -> ResumoDeAmeaca:
    return ResumoDeAmeaca.model_validate_json(REAIS[-1].read_text("utf-8"))


def test_resumo_real_valido_e_sem_ipv4(resumo):
    assert not QUALQUER_IPV4.search(REAIS[-1].read_text("utf-8"))
    assert resumo.total_eventos == sum(resumo.por_servico.values())


def test_credencial_completa_do_resumo_entra_nas_conhecidas(resumo):
    conhecidas = credenciais_conhecidas(resumo)
    assert credenciais_completas(resumo) <= conhecidas
    assert CREDENCIAL_DA_CAMERA in conhecidas  # a câmera continua "credencial conhecida"


def test_rotas_da_demo_com_o_resumo_real():
    fonte, fonte_resumo = carregar_fontes(DEMO)
    assert fonte_resumo.resumo().origem == "real"
    inseguro = fonte.analise(TipoDePerfil.INSEGURO).rota.nos
    seguro = fonte.analise(TipoDePerfil.SEGURO).rota.nos
    assert inseguro == ["internet", "camera", "broker", "fechadura"]
    assert seguro == ["internet", "roteador", "broker", "fechadura"]
