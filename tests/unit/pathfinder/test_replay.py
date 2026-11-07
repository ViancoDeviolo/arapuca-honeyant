"""Gravador de replay: determinismo, formato e gravação atômica."""

import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Snapshot
from honeyant.pathfinder.aco import ACO, ParametrosACO
from honeyant.pathfinder.adapters.replay import GravadorDeReplay
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import GrafoDeRisco, montar_grafo

DEMO = Path(__file__).parents[3] / "docs" / "demo"


def _ler(nome: str):
    return json.loads((DEMO / nome).read_text(encoding="utf-8"))


def _demo(tipo: str) -> GrafoDeRisco:
    perfil = PerfilDaCasa.model_validate(_ler(f"perfil-{tipo}.json"))
    evid = combinar_evidencias(
        EvidenciaDeRede.model_validate(e) for e in _ler(f"evidencias-{tipo}.json")
    )
    resumo = ResumoDeAmeaca.model_validate(_ler("resumo-congelado.json"))
    return montar_grafo(perfil, evid, resumo, ModeloDeRisco())


def _gravar(semente: int = 42, iteracoes: int = 50, tipo: str = "inseguro") -> GravadorDeReplay:
    gravador = GravadorDeReplay()
    parametros = ParametrosACO(semente=semente, iteracoes=iteracoes)
    ACO(parametros, observadores=[gravador]).calcular(_demo(tipo), "internet", "fechadura")
    return gravador


def test_grava_um_snapshot_por_iteracao():
    gravador = _gravar(iteracoes=5)

    linhas = gravador.serializar().splitlines()
    assert gravador.total == 5
    assert len(linhas) == 5
    assert [Snapshot.model_validate_json(linha).iteracao for linha in linhas] == [0, 1, 2, 3, 4]


def test_mesma_semente_gera_replay_identico_byte_a_byte():
    assert _gravar(42).serializar().encode() == _gravar(42).serializar().encode()


def test_sementes_diferentes_geram_replays_diferentes():
    assert _gravar(1).serializar() != _gravar(2).serializar()


def test_ida_e_volta_preserva_os_snapshots():
    gravador = _gravar(iteracoes=10)

    snapshots = [Snapshot.model_validate_json(x) for x in gravador.serializar().splitlines()]
    assert all(s.semente == 42 for s in snapshots)
    assert len({s.execucao_id for s in snapshots}) == 1
    assert snapshots[-1].melhor is not None
    assert snapshots[-1].melhor.nos[0] == "internet"
    assert snapshots[-1].melhor.nos[-1] == "fechadura"


def test_replay_da_casa_insegura_termina_na_rota_pela_camera():
    ultimo = Snapshot.model_validate_json(_gravar().serializar().splitlines()[-1])

    assert ultimo.melhor is not None
    assert ultimo.melhor.nos == ["internet", "camera", "broker", "fechadura"]


def test_replay_da_casa_segura_nao_passa_pela_camera():
    ultimo = Snapshot.model_validate_json(_gravar(tipo="seguro").serializar().splitlines()[-1])

    assert ultimo.melhor is not None
    assert "camera->broker" not in ultimo.melhor.arestas
    assert "camera->broker" not in ultimo.feromonio


def test_salvar_grava_o_mesmo_conteudo_e_nao_deixa_temporario(tmp_path):
    gravador = _gravar(iteracoes=3)

    destino = gravador.salvar(tmp_path / "replays" / "inseguro-42.jsonl")

    assert destino.read_text(encoding="utf-8") == gravador.serializar()
    assert [p.name for p in destino.parent.iterdir()] == ["inseguro-42.jsonl"]


def test_salvar_substitui_replay_anterior(tmp_path):
    destino = tmp_path / "replay.jsonl"
    _gravar(1, iteracoes=3).salvar(destino)

    _gravar(2, iteracoes=3).salvar(destino)

    assert destino.read_text(encoding="utf-8") == _gravar(2, iteracoes=3).serializar()


def test_falha_na_gravacao_nao_deixa_arquivo_pela_metade(tmp_path, monkeypatch):
    destino = tmp_path / "replay.jsonl"
    destino.write_text("replay antigo\n", encoding="utf-8")

    def falhar(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("honeyant.pathfinder.adapters.replay.os.replace", falhar)

    with pytest.raises(OSError, match="disco cheio"):
        _gravar(iteracoes=3).salvar(destino)

    assert destino.read_text(encoding="utf-8") == "replay antigo\n"
    assert [p.name for p in tmp_path.iterdir()] == ["replay.jsonl"]
