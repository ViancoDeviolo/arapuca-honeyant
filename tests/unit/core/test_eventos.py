from datetime import UTC, datetime
from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from honeyant.core.eventos import EventoDeAtaque, Servico

AGORA = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def evento(**extra):
    padrao = {"ts": AGORA, "servico": Servico.TELNET, "ip_origem": "203.0.113.7"}
    return EventoDeAtaque(**(padrao | extra))


def test_trunca_credenciais_e_comandos():
    e = evento(usuario="u" * 100, senha="s" * 100, comandos=["c" * 300] * 30)
    assert len(e.usuario) == 64 and len(e.senha) == 64
    assert len(e.comandos) == 20 and all(len(c) == 256 for c in e.comandos)


def test_rejeita_ts_sem_fuso():
    with pytest.raises(ValidationError):
        EventoDeAtaque(ts=datetime(2026, 11, 5), servico=Servico.MQTT, ip_origem="203.0.113.7")


def test_ipv4_mapeado_em_ipv6_vira_ipv4():
    assert evento(ip_origem="::ffff:203.0.113.7").ip_origem == IPv4Address("203.0.113.7")


def test_pais_normalizado_ou_rejeitado():
    assert evento(pais="br").pais == "BR"
    with pytest.raises(ValidationError):
        evento(pais="Brasil")


def test_credenciais_ausentes_sao_permitidas():
    e = evento()
    assert e.usuario is None and e.senha is None and e.comandos == []


def test_evento_e_imutavel():
    with pytest.raises(ValidationError):
        evento().senha = "x"
