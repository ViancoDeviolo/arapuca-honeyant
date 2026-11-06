import pytest
from pydantic import ValidationError

from honeyant.core.eventos import Servico
from honeyant.core.resumo import Intencao, ResumoDeAmeaca


@pytest.fixture
def resumo(agora):
    def criar(**extra) -> ResumoDeAmeaca:
        padrao = {
            "gerado_em": agora,
            "total_eventos": 10,
            "por_servico": {"telnet": 7, "mqtt": 3},
            "acumulado_por_servico": {"telnet": 70, "mqtt": 30},
            "por_pais": {"CN": 6, "BR": 4},
            "por_asn": {4134: 6, 0: 4},
            "intencao": {"forca_bruta": 7, "varredura": 3},
            "top_credenciais": [{"usuario": "root", "senha": "123456", "tentativas": 5}],
        }
        return ResumoDeAmeaca(**(padrao | extra))

    return criar


def test_resumo_valido(resumo):
    r = resumo()
    assert r.janela_horas == 24
    assert r.por_servico[Servico.TELNET] == 7
    assert r.intencao[Intencao.FORCA_BRUTA] == 7
    assert r.top_credenciais[0].senha == "123456"


def test_nao_tem_campo_de_ip(resumo):
    """LGPD: o resumo sai da EC2, então não pode carregar IP de atacante."""
    assert not any("ip" in nome.split("_") for nome in ResumoDeAmeaca.model_fields)
    with pytest.raises(ValidationError):
        resumo(ips=["203.0.113.7"])


def test_credencial_hostil_e_limpa_e_truncada(resumo):
    cred = {"usuario": "<script>\x00" + "u" * 100, "senha": "s\r\n" * 50, "tentativas": 1}
    c = resumo(top_credenciais=[cred]).top_credenciais[0]
    assert "\x00" not in c.usuario and len(c.usuario) == 64
    assert "\r" not in c.senha and len(c.senha) <= 64


def test_credencial_pode_ser_anonima(resumo):
    c = resumo(top_credenciais=[{"usuario": None, "senha": None, "tentativas": 2}])
    assert c.top_credenciais[0].usuario is None


def test_no_maximo_20_credenciais(resumo):
    creds = [{"usuario": f"u{i}", "senha": "x", "tentativas": 1} for i in range(21)]
    with pytest.raises(ValidationError):
        resumo(top_credenciais=creds)


def test_soma_por_servico_igual_ao_total(resumo):
    with pytest.raises(ValidationError, match="total_eventos"):
        resumo(por_servico={"telnet": 1})


def test_contagens_nao_negativas(resumo):
    with pytest.raises(ValidationError):
        resumo(por_pais={"BR": -1})


@pytest.mark.parametrize("pais", ["Brasil", "B", "b1"])
def test_chave_de_pais_iso(resumo, pais):
    with pytest.raises(ValidationError):
        resumo(por_pais={pais: 1})


def test_pais_normalizado_para_maiusculas(resumo):
    assert resumo(por_pais={"br": 10}).por_pais == {"BR": 10}


def test_resumo_vazio_e_valido(resumo):
    r = resumo(
        total_eventos=0,
        por_servico={},
        acumulado_por_servico={},
        por_pais={},
        por_asn={},
        intencao={},
        top_credenciais=[],
    )
    assert r.total_eventos == 0


def test_ida_e_volta_em_json(resumo):
    r = resumo()
    assert ResumoDeAmeaca.model_validate_json(r.model_dump_json()) == r
