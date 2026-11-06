"""Testes do grafo da casa: validação de entrada hostil e operações básicas."""

import unittest

from honeyant.pathfinder.dominio.grafo import (
    MAX_ARESTAS,
    MAX_NOS,
    Aresta,
    Grafo,
    GrafoInvalido,
)


def grafo_simples() -> Grafo:
    return Grafo(
        nos=["internet", "camera", "fechadura"],
        arestas=[
            Aresta("internet", "camera", 0.9),
            Aresta("camera", "fechadura", 0.8),
        ],
        origem="internet",
        alvo="fechadura",
    )


class TestValidacaoDoGrafo(unittest.TestCase):
    def test_grafo_valido_e_criado(self):
        g = grafo_simples()
        self.assertEqual(g.nos, ("internet", "camera", "fechadura"))
        self.assertEqual(len(g.arestas), 2)

    def test_identificadores_hostis_sao_rejeitados(self):
        hostis = [
            "<script>alert(1)</script>",
            "a" * 33,
            "no\x00de",
            "../etc/passwd",
            "",
            "com espaco",
            "linha\nnova",
        ]
        for nome in hostis:
            with self.subTest(nome=repr(nome)):
                with self.assertRaises(GrafoInvalido):
                    Grafo([nome, "fechadura"], [], nome, "fechadura")

    def test_mensagem_de_erro_nao_repete_o_dado_hostil(self):
        try:
            Grafo(["<script>x</script>", "f"], [], "<script>x</script>", "f")
        except GrafoInvalido as erro:
            self.assertNotIn("script", str(erro))

    def test_risco_fora_de_zero_a_um_e_rejeitado(self):
        invalidos = [-0.1, 1.1, float("nan"), float("inf"), "0.5", None, True]
        for risco in invalidos:
            with self.subTest(risco=risco):
                with self.assertRaises(GrafoInvalido):
                    Grafo(
                        ["a", "b"],
                        [Aresta("a", "b", risco)],
                        "a",
                        "b",
                    )

    def test_risco_nos_limites_e_aceito(self):
        for risco in (0, 0.0, 1, 1.0):
            with self.subTest(risco=risco):
                Grafo(["a", "b"], [Aresta("a", "b", risco)], "a", "b")

    def test_aresta_para_no_inexistente_e_rejeitada(self):
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "b"], [Aresta("a", "z", 0.5)], "a", "b")

    def test_origem_ou_alvo_fora_dos_nos_e_rejeitado(self):
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "b"], [], "x", "b")
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "b"], [], "a", "x")

    def test_origem_igual_ao_alvo_e_rejeitada(self):
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "b"], [], "a", "a")

    def test_nos_e_arestas_duplicados_sao_rejeitados(self):
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "a", "b"], [], "a", "b")
        with self.assertRaises(GrafoInvalido):
            Grafo(
                ["a", "b"],
                [Aresta("a", "b", 0.5), Aresta("a", "b", 0.6)],
                "a",
                "b",
            )

    def test_aresta_para_si_mesma_e_rejeitada(self):
        with self.assertRaises(GrafoInvalido):
            Grafo(["a", "b"], [Aresta("a", "a", 0.5)], "a", "b")

    def test_limites_de_tamanho(self):
        muitos_nos = [f"n{i}" for i in range(MAX_NOS + 1)]
        with self.assertRaises(GrafoInvalido):
            Grafo(muitos_nos, [], "n0", "n1")
        nos = [f"n{i}" for i in range(MAX_NOS)]
        muitas = [
            Aresta(f"n{i}", f"n{j}", 0.5)
            for i in range(MAX_NOS)
            for j in range(MAX_NOS)
            if i != j
        ][: MAX_ARESTAS + 1]
        with self.assertRaises(GrafoInvalido):
            Grafo(nos, muitas, "n0", "n1")

    def test_sem_nos_e_rejeitado(self):
        with self.assertRaises(GrafoInvalido):
            Grafo([], [], "a", "b")


class TestOperacoesDoGrafo(unittest.TestCase):
    def test_custo_da_aresta_e_um_menos_risco(self):
        self.assertAlmostEqual(Aresta("a", "b", 0.9).custo, 0.1)

    def test_custo_da_rota_soma_os_custos(self):
        g = grafo_simples()
        custo = g.custo_da_rota(("internet", "camera", "fechadura"))
        self.assertAlmostEqual(custo, 0.1 + 0.2)

    def test_custo_de_rota_com_aresta_inexistente_e_erro(self):
        g = grafo_simples()
        with self.assertRaises(GrafoInvalido):
            g.custo_da_rota(("internet", "fechadura"))

    def test_existe_caminho(self):
        self.assertTrue(grafo_simples().existe_caminho())

    def test_bloqueio_remove_a_aresta_das_saidas_e_o_caminho(self):
        g = grafo_simples().com_bloqueio("camera", "fechadura")
        self.assertEqual(g.saidas("camera"), ())
        self.assertFalse(g.existe_caminho())

    def test_bloqueio_nao_altera_o_grafo_original(self):
        original = grafo_simples()
        original.com_bloqueio("camera", "fechadura")
        self.assertTrue(original.existe_caminho())

    def test_rota_com_aresta_bloqueada_e_erro(self):
        g = grafo_simples().com_bloqueio("camera", "fechadura")
        with self.assertRaises(GrafoInvalido):
            g.custo_da_rota(("internet", "camera", "fechadura"))

    def test_bloquear_aresta_inexistente_e_erro(self):
        with self.assertRaises(GrafoInvalido):
            grafo_simples().com_bloqueio("internet", "fechadura")


if __name__ == "__main__":
    unittest.main()
