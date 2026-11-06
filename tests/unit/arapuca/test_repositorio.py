from datetime import timedelta

import pytest

from honeyant.arapuca.adapters.memoria import RepositorioEmMemoria
from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.core.eventos import Servico


@pytest.fixture(params=["memoria", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memoria":
        return RepositorioEmMemoria(teto_eventos=5)
    return RepositorioSqlite(tmp_path / "isca.db", teto_eventos=5)


def test_salva_e_conta(repo, fabrica_evento):
    repo.salvar(fabrica_evento())
    repo.salvar(fabrica_evento(servico=Servico.MQTT))
    assert repo.contar() == 2
    assert repo.acumulado_por_servico() == {Servico.TELNET: 1, Servico.MQTT: 1}


def test_retencao_remove_antigos_mas_nao_o_acumulado(repo, fabrica_evento, agora):
    repo.salvar(fabrica_evento(ts=agora - timedelta(days=8)))
    repo.salvar(fabrica_evento(ts=agora))
    assert repo.aplicar_limites(agora) == 1
    assert repo.contar() == 1
    assert repo.acumulado_por_servico()[Servico.TELNET] == 2


def test_teto_descarta_os_mais_antigos(repo, fabrica_evento, agora):
    for i in range(8):
        repo.salvar(fabrica_evento(ts=agora - timedelta(minutes=10 - i), usuario=f"u{i}"))
    repo.aplicar_limites(agora)
    assert repo.contar() == 5


def test_sqlite_persiste_apos_reabrir(tmp_path, fabrica_evento):
    caminho = tmp_path / "isca.db"
    RepositorioSqlite(caminho).salvar(fabrica_evento())
    reaberto = RepositorioSqlite(caminho)
    assert reaberto.contar() == 1
    assert reaberto.acumulado_por_servico()[Servico.TELNET] == 1


def test_sqlite_usa_wal(tmp_path):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    assert repo.modo_journal() == "wal"
