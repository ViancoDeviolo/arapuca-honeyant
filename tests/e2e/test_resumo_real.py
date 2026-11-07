"""Trava da demo com o resumo real da isca (docs/demo/resumo-real-AAAA-MM-DD.json).

Só roda quando o arquivo existe (ele é gerado na EC2 com `honeyant-exportar-resumo`).
Se `test_rotas_da_demo_com_o_resumo_real` falhar, NÃO calibre fixture nenhuma: avise o
Lucas antes (spec do painel, 3.7). Depois de trocar o resumo, regenere os replays com
`uv run honeyant-gravar-replay`.
"""

from pathlib import Path

import pytest

from honeyant.apps.local import carregar_fontes
from honeyant.core.casa import TipoDePerfil
from honeyant.core.resumo import ResumoDeAmeaca

DEMO = Path(__file__).parents[2] / "docs" / "demo"
REAIS = sorted(DEMO.glob("resumo-real-*.json"))

pytestmark = pytest.mark.skipif(not REAIS, reason="sem resumo real em docs/demo")


def test_resumo_real_valido_e_tem_credencial():
    resumo = ResumoDeAmeaca.model_validate_json(REAIS[-1].read_text("utf-8"))
    primeira = resumo.top_credenciais[0]
    # É a senha da câmera no perfil inseguro (decisão de 06/11).
    assert primeira.usuario and primeira.senha


def test_rotas_da_demo_com_o_resumo_real():
    fonte, fonte_resumo = carregar_fontes(DEMO)
    assert fonte_resumo.resumo().origem == "real"
    assert fonte.analise(TipoDePerfil.INSEGURO).rota.nos == [
        "internet",
        "camera",
        "broker",
        "fechadura",
    ]
    assert fonte.analise(TipoDePerfil.SEGURO).rota.nos == [
        "internet",
        "roteador",
        "broker",
        "fechadura",
    ]
