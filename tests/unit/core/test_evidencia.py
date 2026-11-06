from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from honeyant.core.evidencia import EvidenciaDeRede, Fonte, combinar_evidencias


@pytest.fixture
def evid(agora):
    def criar(**extra) -> EvidenciaDeRede:
        padrao = {"aresta": "camera->broker", "observado_em": agora, "fonte": "passivo"}
        return EvidenciaDeRede(**(padrao | extra))

    return criar


def test_campos_nao_observados_sao_none(evid):
    e = evid()
    assert e.fonte is Fonte.PASSIVO
    assert (e.texto_puro, e.credencial_vazada, e.autenticacao_exigida) == (None, None, None)
    assert (e.acl_bloqueia, e.alcancavel) == (None, None)


def test_origem_e_destino(evid):
    assert evid().origem == "camera" and evid().destino == "broker"


@pytest.mark.parametrize("aresta", ["camera-broker", "camera->", "->broker", "a->b->c", "A->b"])
def test_rejeita_aresta_mal_formada(evid, aresta):
    with pytest.raises(ValidationError):
        evid(aresta=aresta)


def test_exige_fuso_e_normaliza_utc(evid, agora):
    with pytest.raises(ValidationError):
        evid(observado_em=datetime(2026, 11, 6))
    from datetime import timezone

    brt = timezone(timedelta(hours=-3))
    assert evid(observado_em=agora.astimezone(brt)).observado_em.utcoffset() == timedelta(0)


def test_combinar_valor_observado_substitui_none(evid, agora):
    passiva = evid(texto_puro=True)
    ativa = evid(fonte="ativo", observado_em=agora - timedelta(hours=1), autenticacao_exigida=False)
    c = combinar_evidencias([passiva, ativa])["camera->broker"]
    assert c.texto_puro is True and c.autenticacao_exigida is False
    assert c.credencial_vazada is None


def test_combinar_conflito_vale_ativa_mesmo_mais_antiga(evid, agora):
    passiva_nova = evid(texto_puro=True)
    ativa_antiga = evid(fonte="ativo", observado_em=agora - timedelta(hours=1), texto_puro=False)
    c = combinar_evidencias([passiva_nova, ativa_antiga])["camera->broker"]
    assert c.texto_puro is False


def test_combinar_entre_ativas_vale_a_mais_recente(evid, agora):
    velha = evid(fonte="ativo", observado_em=agora - timedelta(hours=1), alcancavel=True)
    nova = evid(fonte="ativo", alcancavel=False)
    for ordem in ([velha, nova], [nova, velha]):
        assert combinar_evidencias(ordem)["camera->broker"].alcancavel is False


def test_combinar_separa_por_aresta(evid):
    r = combinar_evidencias([evid(), evid(aresta="broker->fechadura", texto_puro=True)])
    assert set(r) == {"camera->broker", "broker->fechadura"}
    assert r["broker->fechadura"].texto_puro is True


def test_combinar_lista_vazia():
    assert combinar_evidencias([]) == {}
