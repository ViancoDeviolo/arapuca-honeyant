import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import LIMITE_CAMINHOS, Algoritmo, Snapshot
from honeyant.pathfinder.aco import ACO, ParametrosACO, depositar, evaporar
from honeyant.pathfinder.dijkstra import Dijkstra
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.grafo import ArestaPonderada, GrafoDeRisco, montar_grafo

DEMO = Path(__file__).parents[3] / "docs" / "demo"


class Gravador:
    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []

    def notificar(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)


def _grafo(*arestas) -> GrafoDeRisco:
    return GrafoDeRisco([ArestaPonderada(o, d, r) for o, d, r in arestas])


# Grafo desenhado à mão, com armadilhas: a aresta mais arriscada saindo de "a" (a->c, 0.95)
# não leva à melhor rota, e "e" é beco sem saída. Melhor: a->b->d (0.81).
CONHECIDO = _grafo(
    ("a", "b", 0.9),
    ("b", "d", 0.9),
    ("a", "c", 0.95),
    ("c", "d", 0.5),
    ("a", "d", 0.3),
    ("b", "e", 0.99),
    ("c", "e", 0.99),
)


def _demo(tipo: str) -> GrafoDeRisco:
    def ler(nome):
        return json.loads((DEMO / nome).read_text(encoding="utf-8"))

    perfil = PerfilDaCasa.model_validate(ler(f"perfil-{tipo}.json"))
    evid = combinar_evidencias(
        EvidenciaDeRede.model_validate(e) for e in ler(f"evidencias-{tipo}.json")
    )
    resumo = ResumoDeAmeaca.model_validate(ler("resumo-congelado.json"))
    return montar_grafo(perfil, evid, resumo, ModeloDeRisco())


def test_evaporar_reduz_e_respeita_minimo():
    tau = evaporar({"a->b": 1.0, "b->c": 0.01}, rho=0.1, minimo=0.01)
    assert tau == pytest.approx({"a->b": 0.9, "b->c": 0.01})


def test_depositar_reforca_o_caminho_e_respeita_maximo():
    tau = depositar(
        {"a->b": 0.1, "b->c": 0.1, "a->c": 0.1}, ["a", "b", "c"], custo=0.5, q=1.0, maximo=1.0
    )
    assert tau == pytest.approx({"a->b": 1.0, "b->c": 1.0, "a->c": 0.1})


def test_converge_para_o_gabarito_do_dijkstra():
    rota = ACO().calcular(CONHECIDO, "a", "d")
    assert rota.algoritmo is Algoritmo.ACO
    assert rota.nos == Dijkstra().calcular(CONHECIDO, "a", "d").nos


@pytest.mark.parametrize("tipo", ["inseguro", "seguro"])
def test_converge_no_grafo_da_demo(tipo):
    g = _demo(tipo)
    aco = ACO().calcular(g, "internet", "fechadura")
    gabarito = Dijkstra().calcular(g, "internet", "fechadura")
    assert aco.nos == gabarito.nos
    assert aco.custo == pytest.approx(gabarito.custo)


@pytest.mark.parametrize("tipo", ["inseguro", "seguro"])
def test_converge_com_qualquer_semente(tipo):
    """Não basta acertar com a semente 42: a demo não pode depender de sorte."""
    g = _demo(tipo)
    gabarito = Dijkstra().calcular(g, "internet", "fechadura").nos
    erros = [
        s
        for s in range(30)
        if ACO(ParametrosACO(semente=s)).calcular(g, "internet", "fechadura").nos != gabarito
    ]
    assert erros == []


def test_mesma_semente_mesmos_snapshots():
    def rodar():
        g = Gravador()
        ACO(ParametrosACO(semente=7), observadores=[g]).calcular(CONHECIDO, "a", "d")
        return [s.model_dump_json() for s in g.snapshots]

    assert rodar() == rodar()


def test_um_snapshot_por_iteracao_e_dentro_do_contrato():
    g = Gravador()
    p = ParametrosACO(formigas=50, iteracoes=5)
    ACO(p, observadores=[g]).calcular(CONHECIDO, "a", "d")
    assert [s.iteracao for s in g.snapshots] == [0, 1, 2, 3, 4]
    assert all(len(s.caminhos) <= LIMITE_CAMINHOS for s in g.snapshots)
    assert all(set(s.feromonio) == CONHECIDO.chaves() for s in g.snapshots)
    assert g.snapshots[-1].melhor is not None


def test_caminhos_so_usam_arestas_do_grafo_e_chegam_ao_alvo():
    g = Gravador()
    ACO(observadores=[g]).calcular(CONHECIDO, "a", "d")
    for s in g.snapshots:
        for c in s.caminhos:
            assert c[0] == "a" and c[-1] == "d" and len(set(c)) == len(c)
            assert {f"{x}->{y}" for x, y in zip(c, c[1:], strict=False)} <= CONHECIDO.chaves()


def test_sem_rota_devolve_none_sem_excecao():
    g = Gravador()
    grafo = _grafo(("a", "b", 0.9), ("c", "d", 0.9))
    assert ACO(ParametrosACO(iteracoes=3), observadores=[g]).calcular(grafo, "a", "d") is None
    assert len(g.snapshots) == 3 and all(s.melhor is None for s in g.snapshots)


def test_risco_zero_nao_divide_por_zero():
    grafo = _grafo(("a", "b", 0.0), ("b", "c", 0.0))
    assert ACO(ParametrosACO(iteracoes=2)).calcular(grafo, "a", "c").nos == ["a", "b", "c"]


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("formigas", 0),
        ("formigas", 1001),
        ("iteracoes", 0),
        ("iteracoes", 1001),
        ("rho", 0),
        ("rho", 1),
        ("tau_min", 0),
        ("alfa", -1),
    ],
)
def test_parametros_validados(campo, valor):
    with pytest.raises(ValidationError):
        ParametrosACO(**{campo: valor})


def test_desempenho_no_grafo_da_demo():
    g = _demo("inseguro")
    inicio = time.perf_counter()
    ACO().calcular(g, "internet", "fechadura")
    assert time.perf_counter() - inicio < 1.0
