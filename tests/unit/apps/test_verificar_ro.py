import json

from honeyant.apps.verificar_ro import main, relatorio
from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.core.eventos import Servico


def test_relatorio_do_banco_da_isca(tmp_path, fabrica_evento):
    repo = RepositorioSqlite(tmp_path / "isca.db")
    repo.salvar(fabrica_evento())
    repo.salvar(fabrica_evento(usuario="root"))
    repo.salvar(fabrica_evento(servico=Servico.MQTT))
    assert relatorio(tmp_path / "isca.db") == {
        "modo": "ro",
        "eventos": 3,
        "acumulado": {"telnet": 2, "mqtt": 1},
        "escrita_bloqueada": True,
    }


def test_main_imprime_json_sem_ip_e_sai_com_zero(tmp_path, fabrica_evento, monkeypatch, capsys):
    RepositorioSqlite(tmp_path / "isca.db").salvar(fabrica_evento())
    monkeypatch.setenv("HONEYANT_DB", str(tmp_path / "isca.db"))
    assert main() == 0
    saida = capsys.readouterr().out
    assert json.loads(saida)["escrita_bloqueada"] is True
    assert "203.0.113.7" not in saida
