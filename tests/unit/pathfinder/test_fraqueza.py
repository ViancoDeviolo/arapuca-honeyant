import pytest

from honeyant.core.eventos import Servico
from honeyant.core.evidencia import EvidenciaDeRede
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.pathfinder.fraqueza import bloqueada, fraqueza, frequencia


@pytest.fixture
def evid(agora):
    def criar(**campos) -> EvidenciaDeRede:
        return EvidenciaDeRede(aresta="a->b", observado_em=agora, fonte="ativo", **campos)

    return criar


def test_tudo_seguro_da_zero(evid):
    e = evid(
        credencial_vazada=False, texto_puro=False, autenticacao_exigida=True, acl_bloqueia=True
    )
    assert fraqueza(e) == 0


def test_pontos_da_tabela_da_spec(evid):
    base = {
        "credencial_vazada": False,
        "texto_puro": False,
        "autenticacao_exigida": True,
        "acl_bloqueia": True,
    }
    assert fraqueza(evid(**base | {"credencial_vazada": True})) == 4
    assert fraqueza(evid(**base | {"texto_puro": True})) == 3
    assert fraqueza(evid(**base | {"autenticacao_exigida": False})) == 2
    assert fraqueza(evid(**base | {"acl_bloqueia": False})) == 1


def test_tudo_inseguro_da_dez(evid):
    e = evid(
        credencial_vazada=True, texto_puro=True, autenticacao_exigida=False, acl_bloqueia=False
    )
    assert fraqueza(e) == 10


def test_nao_observado_assume_o_pior(evid):
    assert fraqueza(evid()) == 10
    assert fraqueza(None) == 10


def test_bloqueada_so_quando_inalcancavel_observado(evid):
    assert bloqueada(evid(alcancavel=False))
    assert not bloqueada(evid(alcancavel=True))
    assert not bloqueada(evid())
    assert not bloqueada(None)


def _resumo(agora, total, por_servico) -> ResumoDeAmeaca:
    return ResumoDeAmeaca(
        gerado_em=agora,
        total_eventos=total,
        por_servico=por_servico,
        acumulado_por_servico={},
        por_pais={},
        por_asn={},
        intencao={},
        top_credenciais=[],
    )


def test_frequencia(agora):
    r = _resumo(agora, 10, {"telnet": 8, "mqtt": 2})
    assert frequencia(r, Servico.TELNET) == pytest.approx(0.8)
    assert frequencia(r, Servico.UPNP) == 0.0


def test_frequencia_sem_eventos_e_zero(agora):
    assert frequencia(_resumo(agora, 0, {}), Servico.TELNET) == 0.0
