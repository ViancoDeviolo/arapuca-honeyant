"""Testes do ACO: convergência, feromônio, casos de borda, determinismo, limites."""

import random
import time
import unittest

from honeyant.pathfinder.dominio.aco import (
    ParametrosACO,
    depositar,
    evaporar,
    executar,
    sortear,
)
from honeyant.pathfinder.dominio.grafo import Aresta, Grafo
from honeyant.pathfinder.dominio.snapshot import Snapshot


class Coletor:
    """Observador de teste: guarda todos os snapshots recebidos."""

    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []

    def ao_iterar(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)


class RelogioFalso:
    """Relógio injetado: cada leitura avança 1 segundo (sem depender do tempo real)."""

    def __init__(self) -> None:
        self.agora = -1.0

    def __call__(self) -> float:
        self.agora += 1.0
        return self.agora


def grafo_casa() -> Grafo:
    """Grafo à mão (5 nós). Melhor rota: internet-camera-hub-fechadura, custo 0,6."""
    return Grafo(
        nos=["internet", "camera", "roteador", "hub", "fechadura"],
        arestas=[
            Aresta("internet", "camera", 0.9),
            Aresta("internet", "roteador", 0.4),
            Aresta("camera", "hub", 0.8),
            Aresta("roteador", "hub", 0.3),
            Aresta("hub", "fechadura", 0.7),
        ],
        origem="internet",
        alvo="fechadura",
    )


def grafo_armadilha() -> Grafo:
    """6 nós. O primeiro passo mais atraente (a) leva à rota ruim (custo 1,7).

    A melhor rota (x, y) custa 0,6, mas começa com uma aresta menos atraente.
    """
    return Grafo(
        nos=["internet", "a", "b", "x", "y", "fechadura"],
        arestas=[
            Aresta("internet", "a", 0.9),
            Aresta("a", "b", 0.2),
            Aresta("b", "fechadura", 0.2),
            Aresta("internet", "x", 0.6),
            Aresta("x", "y", 0.9),
            Aresta("y", "fechadura", 0.9),
        ],
        origem="internet",
        alvo="fechadura",
    )


class TestConvergencia(unittest.TestCase):
    def test_converge_para_a_melhor_rota_do_grafo_conhecido(self):
        for semente in range(10):
            with self.subTest(semente=semente):
                r = executar(grafo_casa(), semente=semente)
                self.assertEqual(r.rota, ("internet", "camera", "hub", "fechadura"))
                self.assertAlmostEqual(r.custo, 0.6)
                self.assertTrue(r.tem_rota)
                self.assertEqual(r.parada, "concluido")

    def test_feromonio_final_se_concentra_na_melhor_rota(self):
        coletor = Coletor()
        executar(grafo_casa(), semente=1, observador=coletor)
        ultimo = {(o, d): tau for o, d, tau in coletor.snapshots[-1].feromonio}
        self.assertGreater(
            ultimo[("internet", "camera")], ultimo[("internet", "roteador")]
        )

    def test_enxame_aprende_participacao_na_melhor_rota_cresce(self):
        """Regressão: com Q alto o feromônio saturava e o enxame não aprendia."""
        melhor = ("internet", "x", "y", "fechadura")
        inicio, fim = [], []
        for semente in range(20):
            coletor = Coletor()
            executar(grafo_armadilha(), semente=semente, observador=coletor)
            primeiro, ultimo = coletor.snapshots[0], coletor.snapshots[-1]
            for lista, snap in ((inicio, primeiro), (fim, ultimo)):
                usaram = sum(c == melhor for c in snap.caminhos)
                lista.append(usaram / len(snap.caminhos))
        self.assertGreater(sum(fim) / 20, sum(inicio) / 20 + 0.3)

    def test_feromonio_nao_satura_em_todas_as_arestas(self):
        """Regressão: se tudo bate no teto, o feromônio perde a informação."""
        p = ParametrosACO()
        for semente in range(5):
            coletor = Coletor()
            executar(grafo_armadilha(), p, semente=semente, observador=coletor)
            taus = [tau for _, _, tau in coletor.snapshots[-1].feromonio]
            self.assertLess(sum(t >= p.tau_max for t in taus), len(taus))

    def test_nao_se_deixa_enganar_pelo_primeiro_passo_mais_atraente(self):
        for semente in range(10):
            with self.subTest(semente=semente):
                r = executar(grafo_armadilha(), semente=semente)
                self.assertEqual(r.rota, ("internet", "x", "y", "fechadura"))
                self.assertAlmostEqual(r.custo, 0.6)


class TestFeromonio(unittest.TestCase):
    def test_evaporacao_reduz_o_feromonio(self):
        antes = {("a", "b"): 1.0, ("b", "c"): 4.0}
        depois = evaporar(antes, rho=0.3, tau_min=0.1)
        self.assertAlmostEqual(depois[("a", "b")], 0.7)
        self.assertAlmostEqual(depois[("b", "c")], 2.8)

    def test_evaporacao_respeita_o_minimo(self):
        depois = evaporar({("a", "b"): 0.11}, rho=0.9, tau_min=0.1)
        self.assertAlmostEqual(depois[("a", "b")], 0.1)

    def test_evaporacao_nao_altera_o_dicionario_original(self):
        antes = {("a", "b"): 1.0}
        evaporar(antes, rho=0.5, tau_min=0.1)
        self.assertEqual(antes, {("a", "b"): 1.0})

    def test_reforco_aumenta_so_as_arestas_da_rota(self):
        antes = {("a", "b"): 1.0, ("b", "c"): 1.0, ("a", "c"): 1.0}
        depois = depositar(antes, ("a", "b", "c"), quantidade=2.0, tau_max=10.0)
        self.assertAlmostEqual(depois[("a", "b")], 3.0)
        self.assertAlmostEqual(depois[("b", "c")], 3.0)
        self.assertAlmostEqual(depois[("a", "c")], 1.0)

    def test_reforco_respeita_o_maximo(self):
        depois = depositar({("a", "b"): 9.0}, ("a", "b"), quantidade=5.0, tau_max=10.0)
        self.assertAlmostEqual(depois[("a", "b")], 10.0)

    def test_feromonio_dos_snapshots_fica_entre_minimo_e_maximo(self):
        p = ParametrosACO()
        coletor = Coletor()
        executar(grafo_casa(), p, semente=3, observador=coletor)
        for snap in coletor.snapshots:
            for _, _, tau in snap.feromonio:
                self.assertGreaterEqual(tau, p.tau_min)
                self.assertLessEqual(tau, p.tau_max)


class TestPesoDaEscolha(unittest.TestCase):
    """O risco (heurística) e o feromônio realmente influenciam o primeiro passo."""

    @staticmethod
    def _parte_pela_aresta_atraente(beta: float) -> float:
        # alfa=0 ignora o feromônio: só a heurística (risco^beta) decide.
        p = ParametrosACO(
            formigas=200, iteracoes=1, alfa=0.0, beta=beta, max_caminhos_snapshot=200
        )
        coletor = Coletor()
        executar(grafo_armadilha(), p, semente=1, observador=coletor)
        caminhos = coletor.snapshots[0].caminhos
        return sum(c[1] == "a" for c in caminhos) / len(caminhos)

    def test_beta_maior_favorece_a_aresta_de_maior_risco(self):
        sem_heuristica = self._parte_pela_aresta_atraente(beta=0.0)
        com_heuristica = self._parte_pela_aresta_atraente(beta=5.0)
        self.assertGreater(com_heuristica, sem_heuristica + 0.2)


class TestSorteio(unittest.TestCase):
    def test_pesos_zerados_sorteiam_uniformemente_sem_dividir_por_zero(self):
        rng = random.Random(0)
        escolhidos = {sortear([0.0, 0.0, 0.0], rng) for _ in range(200)}
        self.assertEqual(escolhidos, {0, 1, 2})

    def test_peso_zero_nunca_e_escolhido_se_ha_outro(self):
        rng = random.Random(0)
        escolhidos = {sortear([0.0, 1.0, 0.0], rng) for _ in range(200)}
        self.assertEqual(escolhidos, {1})

    def test_mesma_semente_mesmo_sorteio(self):
        a = [sortear([1.0, 2.0, 3.0], random.Random(7)) for _ in range(5)]
        b = [sortear([1.0, 2.0, 3.0], random.Random(7)) for _ in range(5)]
        self.assertEqual(a, b)

    def test_peso_maior_e_escolhido_mais_vezes(self):
        rng = random.Random(1)
        contagem = [0, 0]
        for _ in range(2000):
            contagem[sortear([1.0, 9.0], rng)] += 1
        self.assertGreater(contagem[1], contagem[0] * 4)


class TestCasosDeBorda(unittest.TestCase):
    def test_aresta_bloqueada_nunca_aparece_em_caminho(self):
        g = Grafo(
            ["internet", "camera", "roteador", "fechadura"],
            [
                Aresta("internet", "camera", 0.95, bloqueada=True),
                Aresta("camera", "fechadura", 0.95),
                Aresta("internet", "roteador", 0.3),
                Aresta("roteador", "fechadura", 0.3),
            ],
            "internet",
            "fechadura",
        )
        coletor = Coletor()
        r = executar(g, semente=5, observador=coletor)
        self.assertEqual(r.rota, ("internet", "roteador", "fechadura"))
        for snap in coletor.snapshots:
            for caminho in snap.caminhos:
                self.assertNotIn("camera", caminho)
            self.assertNotIn(
                ("internet", "camera"), [(o, d) for o, d, _ in snap.feromonio]
            )

    def test_sem_rota_devolve_resultado_claro_sem_excecao(self):
        g = grafo_casa().com_bloqueio("hub", "fechadura")
        coletor = Coletor()
        r = executar(g, semente=1, observador=coletor)
        self.assertIsNone(r.rota)
        self.assertIsNone(r.custo)
        self.assertFalse(r.tem_rota)
        self.assertEqual(r.parada, "sem_rota")
        self.assertEqual(r.iteracoes_executadas, 0)
        self.assertEqual(coletor.snapshots, [])

    def test_formiga_em_beco_sem_saida_e_descartada(self):
        g = Grafo(
            ["internet", "beco", "x", "fechadura"],
            [
                Aresta("internet", "beco", 0.99),
                Aresta("internet", "x", 0.3),
                Aresta("x", "fechadura", 0.3),
            ],
            "internet",
            "fechadura",
        )
        coletor = Coletor()
        r = executar(g, semente=2, observador=coletor)
        self.assertEqual(r.rota, ("internet", "x", "fechadura"))
        for snap in coletor.snapshots:
            for caminho in snap.caminhos:
                self.assertNotIn("beco", caminho)

    def test_ciclo_no_grafo_nao_gera_caminho_com_no_repetido(self):
        g = Grafo(
            ["internet", "a", "b", "fechadura"],
            [
                Aresta("internet", "a", 0.8),
                Aresta("a", "b", 0.8),
                Aresta("b", "a", 0.8),
                Aresta("b", "fechadura", 0.8),
            ],
            "internet",
            "fechadura",
        )
        coletor = Coletor()
        r = executar(g, semente=4, observador=coletor)
        self.assertEqual(r.rota, ("internet", "a", "b", "fechadura"))
        for snap in coletor.snapshots:
            for caminho in snap.caminhos:
                self.assertEqual(len(caminho), len(set(caminho)))

    def test_rota_de_custo_zero_nao_causa_divisao_por_zero(self):
        g = Grafo(
            ["internet", "fechadura"],
            [Aresta("internet", "fechadura", 1.0)],
            "internet",
            "fechadura",
        )
        r = executar(g, semente=1)
        self.assertEqual(r.rota, ("internet", "fechadura"))
        self.assertAlmostEqual(r.custo, 0.0)

    def test_aresta_com_risco_zero_ainda_pode_ser_usada(self):
        g = Grafo(
            ["internet", "fechadura"],
            [Aresta("internet", "fechadura", 0.0)],
            "internet",
            "fechadura",
        )
        r = executar(g, semente=1)
        self.assertEqual(r.rota, ("internet", "fechadura"))
        self.assertAlmostEqual(r.custo, 1.0)


class TestDeterminismo(unittest.TestCase):
    def test_mesma_semente_gera_a_mesma_sequencia_de_snapshots(self):
        a, b = Coletor(), Coletor()
        ra = executar(grafo_casa(), semente=42, observador=a)
        rb = executar(grafo_casa(), semente=42, observador=b)
        self.assertEqual(a.snapshots, b.snapshots)
        self.assertEqual(ra, rb)

    def test_sementes_diferentes_podem_gerar_caminhos_diferentes(self):
        a, b = Coletor(), Coletor()
        executar(grafo_casa(), semente=1, observador=a)
        executar(grafo_casa(), semente=2, observador=b)
        self.assertNotEqual(a.snapshots, b.snapshots)

    def test_nao_usa_o_random_global(self):
        random.seed(123)
        a = executar(grafo_casa(), semente=9)
        random.seed(456)
        b = executar(grafo_casa(), semente=9)
        self.assertEqual(a, b)


class TestObservador(unittest.TestCase):
    def test_um_snapshot_por_iteracao_numerados_a_partir_de_um(self):
        p = ParametrosACO(iteracoes=7)
        coletor = Coletor()
        r = executar(grafo_casa(), p, semente=1, observador=coletor)
        self.assertEqual(r.iteracoes_executadas, 7)
        self.assertEqual([s.iteracao for s in coletor.snapshots], list(range(1, 8)))

    def test_limite_de_caminhos_por_snapshot(self):
        p = ParametrosACO(formigas=30, max_caminhos_snapshot=5)
        coletor = Coletor()
        executar(grafo_casa(), p, semente=1, observador=coletor)
        for snap in coletor.snapshots:
            self.assertLessEqual(len(snap.caminhos), 5)

    def test_melhor_rota_do_snapshot_so_melhora_com_o_tempo(self):
        coletor = Coletor()
        executar(grafo_armadilha(), semente=0, observador=coletor)
        custos = [
            s.melhor_custo for s in coletor.snapshots if s.melhor_custo is not None
        ]
        self.assertEqual(custos, sorted(custos, reverse=True))

    def test_funciona_sem_observador(self):
        self.assertTrue(executar(grafo_casa(), semente=1).tem_rota)


class TestLimites(unittest.TestCase):
    def test_nunca_passa_do_limite_de_iteracoes(self):
        r = executar(grafo_casa(), ParametrosACO(iteracoes=3), semente=1)
        self.assertEqual(r.iteracoes_executadas, 3)

    def test_limite_de_tempo_interrompe_a_execucao(self):
        r = executar(
            grafo_casa(),
            ParametrosACO(iteracoes=50),
            semente=1,
            relogio=RelogioFalso(),
            limite_segundos=2.5,
        )
        self.assertEqual(r.parada, "tempo_limite")
        self.assertEqual(r.iteracoes_executadas, 2)
        self.assertTrue(r.tem_rota)

    def test_limite_de_tempo_exige_relogio(self):
        with self.assertRaises(ValueError):
            executar(grafo_casa(), semente=1, limite_segundos=1.0)

    def test_parametros_invalidos_sao_rejeitados(self):
        invalidos = [
            {"formigas": 0},
            {"formigas": 1001},
            {"iteracoes": 0},
            {"iteracoes": 10001},
            {"rho": 0.0},
            {"rho": 1.0},
            {"alfa": -1.0},
            {"beta": -1.0},
            {"alfa": 11.0},
            {"tau0": 0.0},
            {"tau_min": 2.0},
            {"tau_max": 0.5},
            {"q": 0.0},
            {"max_caminhos_snapshot": -1},
        ]
        for campos in invalidos:
            with self.subTest(campos=campos):
                with self.assertRaises(ValueError):
                    ParametrosACO(**campos)

    def test_parametros_padrao_sao_validos(self):
        p = ParametrosACO()
        self.assertEqual((p.formigas, p.iteracoes), (20, 50))
        self.assertEqual((p.rho, p.alfa, p.beta, p.q), (0.3, 1.0, 2.0, 0.1))


class TestMitigacaoAntesDepois(unittest.TestCase):
    """Precursor do teste da demo: a mitigação encarece ou fecha a rota."""

    def test_bloquear_a_camera_encarece_a_rota(self):
        antes = executar(grafo_casa(), semente=1)
        depois = executar(grafo_casa().com_bloqueio("internet", "camera"), semente=1)
        self.assertIn("camera", antes.rota)
        self.assertNotIn("camera", depois.rota)
        self.assertAlmostEqual(antes.custo, 0.6)
        self.assertAlmostEqual(depois.custo, 1.6)
        self.assertGreater(depois.custo, antes.custo)

    def test_bloquear_todas_as_entradas_fecha_a_rota(self):
        g = grafo_casa().com_bloqueio("internet", "camera")
        g = g.com_bloqueio("internet", "roteador")
        depois = executar(g, semente=1)
        self.assertFalse(depois.tem_rota)
        self.assertEqual(depois.parada, "sem_rota")


class TestDesempenho(unittest.TestCase):
    def test_convergencia_no_grafo_pequeno_em_menos_de_um_segundo(self):
        inicio = time.perf_counter()
        executar(grafo_casa(), semente=1)
        self.assertLess(time.perf_counter() - inicio, 1.0)


if __name__ == "__main__":
    unittest.main()
