"""Leitura do banco da isca em mode=ro: o caminho do painel e do intel na EC2.

Roda só com arquivo local (sem docker), por isso não leva o marcador `integration`.
"""

import threading

import pytest

from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.core.eventos import Servico
from honeyant.intel.adapters.sqlite_leitura import LeitorSqlite


def test_le_o_que_a_isca_gravou(tmp_path, fabrica_evento):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    repo.salvar(fabrica_evento())
    repo.salvar(fabrica_evento(servico=Servico.MQTT))
    leitor = LeitorSqlite(tmp_path / "isca.db")
    assert leitor.modo() == "ro"
    assert leitor.contar() == 2
    assert leitor.acumulado_por_servico() == {Servico.TELNET: 1, Servico.MQTT: 1}


def test_escrita_e_recusada(tmp_path):
    RepositorioSqlite(tmp_path / "isca.db")
    assert LeitorSqlite(tmp_path / "isca.db").escrita_bloqueada() is True


def test_banco_inexistente_da_erro_claro_e_nao_cria_arquivo(tmp_path):
    caminho = tmp_path / "nao-existe.db"
    with pytest.raises(FileNotFoundError, match="nao-existe.db"):
        LeitorSqlite(caminho)
    assert not caminho.exists()


def test_leitura_concorrente_com_escrita(tmp_path, fabrica_evento):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    leitor = LeitorSqlite(tmp_path / "isca.db")
    total = 200

    def escrever():
        for i in range(total):
            repo.salvar(fabrica_evento(usuario=f"u{i}"))

    escritor = threading.Thread(target=escrever)
    escritor.start()
    contagens = []
    while escritor.is_alive():
        contagens.append(leitor.contar())
    escritor.join()
    contagens.append(leitor.contar())

    assert contagens == sorted(contagens)
    assert contagens[-1] == total
