"""Replays da demo: gerados pelo pathfinder de verdade e travados no CI."""

import json
import math
import shutil
from pathlib import Path

import pytest

from honeyant.apps.gravar_replay import gerar_replays, main
from honeyant.core.casa import TipoDePerfil
from honeyant.core.rota import Snapshot

DEMO = Path(__file__).parents[3] / "docs" / "demo"
REGERAR = "rode `uv run honeyant-gravar-replay` e faça commit de `docs/demo/replay-*.jsonl`"


def _linhas(texto: str) -> list[dict]:
    return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]


def _iguais(a, b) -> bool:
    """Igualdade estrutural; floats com tolerância relativa de 1e-9."""
    if isinstance(a, float) or isinstance(b, float):
        return (
            isinstance(a, int | float)
            and isinstance(b, int | float)
            and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        )
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_iguais(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_iguais(x, y) for x, y in zip(a, b, strict=True))
    return a == b


@pytest.fixture(scope="module")
def replays() -> dict[TipoDePerfil, str]:
    return gerar_replays(DEMO)


@pytest.mark.parametrize("perfil", list(TipoDePerfil))
def test_replays_commitados_estao_atualizados(replays, perfil):
    arquivo = DEMO / f"replay-{perfil.value}.jsonl"
    assert arquivo.is_file(), REGERAR
    # Mesma estrutura e mesmos caminhos; floats com tolerância, porque o fuzzy (numpy)
    # pode variar na última casa entre o Windows de quem gera e o Linux do CI.
    assert _iguais(_linhas(replays[perfil]), _linhas(arquivo.read_text(encoding="utf-8"))), REGERAR


def test_replay_inseguro_termina_pela_camera(replays):
    ultimo = Snapshot.model_validate_json(replays[TipoDePerfil.INSEGURO].splitlines()[-1])
    assert ultimo.melhor is not None
    assert "camera" in ultimo.melhor.nos


def test_replays_sao_snapshots_validos_e_deterministicos(replays):
    for perfil in TipoDePerfil:
        snapshots = [Snapshot.model_validate_json(x) for x in replays[perfil].splitlines()]
        assert snapshots
        assert all(s.semente == 42 for s in snapshots)
    assert gerar_replays(DEMO) == replays


def test_main_grava_os_dois_arquivos(tmp_path, monkeypatch):
    for arquivo in DEMO.glob("*.json"):
        shutil.copy(arquivo, tmp_path / arquivo.name)
    monkeypatch.setenv("HONEYANT_DEMO_DIR", str(tmp_path))

    main()

    esperados = gerar_replays(tmp_path)
    for perfil in TipoDePerfil:
        gravado = (tmp_path / f"replay-{perfil.value}.jsonl").read_text(encoding="utf-8")
        assert gravado == esperados[perfil]
