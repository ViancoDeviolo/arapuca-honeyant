import asyncio
from datetime import UTC, datetime

import pytest

from honeyant.core.eventos import EventoDeAtaque, Servico


@pytest.fixture
def agora() -> datetime:
    return datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def fabrica_evento(agora):
    def criar(**extra) -> EventoDeAtaque:
        padrao = {"ts": agora, "servico": Servico.TELNET, "ip_origem": "203.0.113.7"}
        return EventoDeAtaque(**(padrao | extra))

    return criar


@pytest.fixture
def leitor_com():
    """Cria um StreamReader já alimentado com `dados` (e EOF, por padrão)."""

    def criar(dados: bytes, eof: bool = True) -> asyncio.StreamReader:
        leitor = asyncio.StreamReader()
        leitor.feed_data(dados)
        if eof:
            leitor.feed_eof()
        return leitor

    return criar
