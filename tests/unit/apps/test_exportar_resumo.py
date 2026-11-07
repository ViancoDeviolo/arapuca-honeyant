"""`honeyant-exportar-resumo`: do SQLite da isca para um resumo válido e sem IPs."""

from datetime import timedelta

from honeyant.apps.exportar_resumo import main
from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.core.eventos import Servico
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.intel.adapters.sqlite_leitura import LeitorSqlite

IPS = ("203.0.113.7", "2001:db8::1")


def _banco(tmp_path, fabrica_evento, agora):
    banco = tmp_path / "isca.db"
    repo = RepositorioSqlite(banco)
    repo.salvar(fabrica_evento(ip_origem=IPS[0], usuario="admin", senha="admin", pais="CN"))
    repo.salvar(fabrica_evento(ip_origem=IPS[1], servico=Servico.MQTT))
    repo.salvar(fabrica_evento(ts=agora - timedelta(hours=30), usuario="velho", senha="x"))
    return banco


def test_exporta_do_sqlite_de_teste(tmp_path, fabrica_evento, agora, monkeypatch):
    monkeypatch.setenv("HONEYANT_DB", str(_banco(tmp_path, fabrica_evento, agora)))
    destino = tmp_path / "resumo.json"
    assert main([str(destino)], agora=agora) == 0
    texto = destino.read_text("utf-8")
    resumo = ResumoDeAmeaca.model_validate_json(texto)
    assert resumo.total_eventos == 2  # o de 30 h atrás fica fora da janela
    assert resumo.acumulado_por_servico == {Servico.TELNET: 2, Servico.MQTT: 1}
    assert resumo.top_credenciais[0].usuario == "admin"
    assert not any(ip in texto for ip in IPS)


def test_sem_destino_imprime_o_json(tmp_path, fabrica_evento, agora, monkeypatch, capsys):
    monkeypatch.setenv("HONEYANT_DB", str(_banco(tmp_path, fabrica_evento, agora)))
    assert main([], agora=agora) == 0
    ResumoDeAmeaca.model_validate_json(capsys.readouterr().out)


def test_banco_inexistente_sai_com_erro(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HONEYANT_DB", str(tmp_path / "nao-existe.db"))
    assert main([]) == 1
    assert "banco da isca não encontrado" in capsys.readouterr().err


def test_eventos_desde_le_em_ordem_e_respeita_o_inicio(tmp_path, fabrica_evento, agora):
    banco = _banco(tmp_path, fabrica_evento, agora)
    leitor = LeitorSqlite(banco)
    try:
        eventos = leitor.eventos_desde(agora - timedelta(hours=24))
    finally:
        leitor.fechar()
    assert len(eventos) == 2
    assert all(e.ts >= agora - timedelta(hours=24) for e in eventos)
