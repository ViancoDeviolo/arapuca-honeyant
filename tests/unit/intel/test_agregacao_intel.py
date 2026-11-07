"""intel: agregação dos eventos da isca num ResumoDeAmeaca sem IPs, e o fuzzy de intenção."""

from datetime import timedelta

import pytest

from honeyant.core.eventos import Servico
from honeyant.core.resumo import Intencao, ResumoDeAmeaca
from honeyant.intel.intencao import classificar
from honeyant.intel.resumo import agregar

IP_A, IP_B, IP_C = "203.0.113.7", "2001:db8::1", "198.51.100.9"


def test_agrega_contagens_paises_e_credenciais(fabrica_evento, agora):
    eventos = [
        fabrica_evento(pais="CN", asn=4134, usuario="admin", senha="admin"),
        fabrica_evento(pais="CN", asn=4134, usuario="admin", senha="admin"),
        fabrica_evento(pais="BR", asn=None, usuario="root", senha="xc3511"),
        fabrica_evento(servico=Servico.MQTT, pais=None, ip_origem=IP_B),
    ]
    r = agregar(eventos, {Servico.TELNET: 50, Servico.MQTT: 7}, agora)
    assert isinstance(r, ResumoDeAmeaca)
    assert r.total_eventos == 4
    assert r.por_servico == {Servico.TELNET: 3, Servico.MQTT: 1}
    assert r.acumulado_por_servico == {Servico.TELNET: 50, Servico.MQTT: 7}
    assert r.por_pais == {"CN": 2, "BR": 1, "ZZ": 1}
    assert r.por_asn == {4134: 2, 0: 2}
    assert [(c.usuario, c.senha, c.tentativas) for c in r.top_credenciais] == [
        ("admin", "admin", 2),
        ("root", "xc3511", 1),
    ]
    assert r.gerado_em == agora and r.janela_horas == 24


def test_eventos_fora_da_janela_ficam_de_fora(fabrica_evento, agora):
    eventos = [
        fabrica_evento(ts=agora - timedelta(hours=25)),
        fabrica_evento(ts=agora - timedelta(hours=24)),  # exatamente no limite: fora
        fabrica_evento(ts=agora - timedelta(hours=23, minutes=59)),
    ]
    assert agregar(eventos, {}, agora).total_eventos == 1


def test_janela_vazia_da_resumo_valido_com_total_zero(agora):
    r = agregar([], {Servico.TELNET: 198, Servico.MQTT: 2}, agora)
    assert r.total_eventos == 0
    assert r.por_servico == {} and r.top_credenciais == [] and r.intencao == {}
    assert r.acumulado_por_servico[Servico.TELNET] == 198


def test_desempate_deterministico(fabrica_evento, agora):
    eventos = [
        fabrica_evento(usuario="root", senha="b"),
        fabrica_evento(usuario="admin", senha="z"),
        fabrica_evento(usuario="root", senha="a"),
    ]
    r1 = agregar(eventos, {}, agora)
    r2 = agregar(list(reversed(eventos)), {}, agora)
    esperado = [("admin", "z"), ("root", "a"), ("root", "b")]
    assert [(c.usuario, c.senha) for c in r1.top_credenciais] == esperado
    assert r1.top_credenciais == r2.top_credenciais


def test_top_credenciais_limitado_a_20_e_ignora_sessao_sem_credencial(fabrica_evento, agora):
    eventos = [fabrica_evento(usuario=f"u{i:02d}", senha="x") for i in range(30)]
    eventos.append(fabrica_evento())
    r = agregar(eventos, {}, agora)
    assert len(r.top_credenciais) == 20
    assert all(c.usuario for c in r.top_credenciais)


def test_nenhum_ip_no_resumo(fabrica_evento, agora):
    eventos = [
        fabrica_evento(ip_origem=IP_A, usuario="admin", senha="admin"),
        fabrica_evento(ip_origem=IP_B, servico=Servico.MQTT),
    ]
    texto = agregar(eventos, {Servico.TELNET: 1}, agora).model_dump_json()
    assert IP_A not in texto and IP_B not in texto and "2001:db8" not in texto


def test_intencao_soma_o_total_de_eventos(fabrica_evento, agora):
    eventos = [fabrica_evento(ip_origem=IP_A, usuario=f"u{i}", senha="x") for i in range(8)]
    eventos += [fabrica_evento(ip_origem=IP_B, servico=Servico.MQTT)]
    eventos += [
        fabrica_evento(
            ip_origem=IP_C, usuario="root", senha="1", comandos=["wget x", "sh y", "chmod +x z"]
        )
    ]
    r = agregar(eventos, {}, agora)
    assert sum(r.intencao.values()) == r.total_eventos == 10
    assert r.intencao == {Intencao.FORCA_BRUTA: 8, Intencao.VARREDURA: 1, Intencao.BOTNET: 1}


# ---------- fuzzy de intenção (por origem, só em memória) ----------


@pytest.mark.parametrize(
    ("diversidade", "comandos", "taxa", "esperado"),
    [
        (0, 0.0, 1, Intencao.VARREDURA),  # só bateu na porta
        (1, 0.0, 1, Intencao.VARREDURA),  # uma tentativa e foi embora
        (8, 0.0, 4, Intencao.FORCA_BRUTA),  # muitas senhas diferentes
        (2, 0.0, 40, Intencao.FORCA_BRUTA),  # poucas senhas, mas martelando
        (1, 4.0, 1, Intencao.BOTNET),  # entrou e já mandou baixar e rodar algo
        (6, 3.0, 20, Intencao.BOTNET),  # comandos pesam mais que as tentativas
    ],
)
def test_classificar(diversidade, comandos, taxa, esperado):
    assert classificar(diversidade, comandos, taxa) is esperado
