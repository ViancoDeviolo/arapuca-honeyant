import json
from pathlib import Path

import pytest

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Snapshot
from honeyant.pathfinder.aco import ACO, ParametrosACO
from honeyant.pathfinder.adapters.gravador_json import GravadorJson
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import GrafoDeRisco, montar_grafo

DEMO = Path(__file__).parents[3] / "docs" / "demo"


def _ler(nome: str):
    return json.loads((DEMO / nome).read_text(encoding="utf-8"))


def _demo(tipo: str) -> GrafoDeRisco:
    perfil = PerfilDaCasa.model_validate(_ler(f"perfil-{tipo}.json"))
    evidencia = combinar_evidencias(
        EvidenciaDeRede.model_validate(e) for e in _ler(f"evidencias-{tipo}.json")
    )
    resumo = ResumoDeAmeaca.model_validate(_ler("resumo-congelado.json"))
    return montar_grafo(perfil, evidencia, resumo, ModeloDeRisco())


def _gravar(tmp_path: Path, *, semente: int = 42, iteracoes: int = 10, tipo: str = "inseguro") -> Path:
    destino = tmp_path / f"replay-{tipo}-{semente}.jsonl"
    gravador = GravadorJson(destino)
    ACO(ParametrosACO(semente=semente, iteracoes=iteracoes), observadores=[gravador]).calcular(
        _demo(tipo), "internet", "fechadura"
    )
    return destino


def test_replay_grava_um_snapshot_por_iteracao(tmp_path):
    arquivo = _gravar(tmp_path, iteracoes=5)
    linhas = arquivo.read_text(encoding="utf-8").splitlines()

    assert len(linhas) == 5
    assert [Snapshot.model_validate_json(linha).iteracao for linha in linhas] == [0, 1, 2, 3, 4]


def test_replay_mesma_semente_gera_arquivo_idempotente(tmp_path):
    a = _gravar(tmp_path, semente=7, iteracoes=3)
    b = _gravar(tmp_path, semente=7, iteracoes=3)

    assert a.read_bytes() == b.read_bytes()


def test_replay_round_trip_preserva_os_snapshots(tmp_path):
    arquivo = _gravar(tmp_path, semente=42, iteracoes=6)
    snapshots = [Snapshot.model_validate_json(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]

    assert len(snapshots) == 6
    assert snapshots[0].semente == 42
    assert snapshots[-1].melhor is not None
    assert snapshots[-1].melhor.nos[0] == "internet"
    assert snapshots[-1].melhor.nos[-1] == "fechadura"


def test_replay_da_casa_insegura_passa_pela_camera(tmp_path):
    arquivo = _gravar(tmp_path, tipo="inseguro")
    ultimo = Snapshot.model_validate_json(arquivo.read_text(encoding="utf-8").splitlines()[-1])

    assert ultimo.melhor is not None
    assert ultimo.melhor.nos == ["internet", "camera", "broker", "fechadura"]


def test_replay_da_casa_segura_nao_passa_pela_camera(tmp_path):
    arquivo = _gravar(tmp_path, tipo="seguro")
    ultimo = Snapshot.model_validate_json(arquivo.read_text(encoding="utf-8").splitlines()[-1])

    assert ultimo.melhor is not None
    assert "camera->broker" not in ultimo.melhor.arestas
