"""Testes do motor fuzzy (scikit-fuzzy): pertinência, risco, cobertura, monotonia.

Os valores de referência (0,129; 0,450; 0,733; 0,928) foram calculados por uma
implementação independente (Mamdani com mínimo/máximo e centroide), não pelo
próprio scikit-fuzzy.
"""

import itertools
import random
import unittest

from honeyant.pathfinder.dominio.fuzzy import CalculadoraDeRisco


class TestPertinencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calc = CalculadoraDeRisco()

    def grau(self, conjunto: str, valor: float) -> float:
        return self.calc.grau_de_pertinencia("fraqueza", conjunto, valor)

    def test_baixa_pontos_conhecidos(self):
        self.assertAlmostEqual(self.grau("baixa", 0.0), 1.0, places=6)
        self.assertAlmostEqual(self.grau("baixa", 0.2), 1.0, places=6)
        self.assertAlmostEqual(self.grau("baixa", 0.3), 0.5, places=6)
        self.assertAlmostEqual(self.grau("baixa", 0.4), 0.0, places=6)

    def test_media_pontos_conhecidos(self):
        self.assertAlmostEqual(self.grau("media", 0.2), 0.0, places=6)
        self.assertAlmostEqual(self.grau("media", 0.35), 0.5, places=6)
        self.assertAlmostEqual(self.grau("media", 0.5), 1.0, places=6)
        self.assertAlmostEqual(self.grau("media", 0.8), 0.0, places=6)

    def test_alta_pontos_conhecidos(self):
        self.assertAlmostEqual(self.grau("alta", 0.6), 0.0, places=6)
        self.assertAlmostEqual(self.grau("alta", 0.7), 0.5, places=6)
        self.assertAlmostEqual(self.grau("alta", 0.8), 1.0, places=6)
        self.assertAlmostEqual(self.grau("alta", 1.0), 1.0, places=6)

    def test_todo_valor_pertence_a_algum_conjunto(self):
        for i in range(101):
            valor = i / 100
            with self.subTest(valor=valor):
                graus = [self.grau(c, valor) for c in ("baixa", "media", "alta")]
                self.assertGreater(max(graus), 0.0)


class TestRisco(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calc = CalculadoraDeRisco()

    def risco(self, f: float, w: float, e: float) -> float:
        return self.calc.calcular(frequencia=f, fraqueza=w, exposicao=e)

    def test_tudo_baixo_da_risco_baixo(self):
        self.assertAlmostEqual(self.risco(0, 0, 0), 0.129, delta=0.01)

    def test_tudo_alto_da_risco_muito_alto(self):
        self.assertAlmostEqual(self.risco(1, 1, 1), 0.928, delta=0.01)

    def test_tudo_medio_da_risco_medio(self):
        self.assertAlmostEqual(self.risco(0.5, 0.5, 0.5), 0.450, delta=0.01)

    def test_duas_altas_e_uma_media_da_risco_alto(self):
        self.assertAlmostEqual(self.risco(1, 1, 0.5), 0.733, delta=0.01)

    def test_elo_mais_fraco_uma_entrada_baixa_derruba_o_risco(self):
        for f, w, e in [(0, 1, 1), (1, 0, 1), (1, 1, 0)]:
            with self.subTest(entradas=(f, w, e)):
                self.assertAlmostEqual(self.risco(f, w, e), 0.129, delta=0.01)

    def test_risco_sempre_entre_zero_e_um_sem_excecao(self):
        grade = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        for f, w, e in itertools.product(grade, repeat=3):
            with self.subTest(entradas=(f, w, e)):
                self.assertTrue(0.0 <= self.risco(f, w, e) <= 1.0)

    def test_risco_entre_zero_e_um_para_entradas_aleatorias_com_semente(self):
        rng = random.Random(0)
        for _ in range(200):
            f, w, e = rng.random(), rng.random(), rng.random()
            self.assertTrue(0.0 <= self.risco(f, w, e) <= 1.0)

    def test_mesma_entrada_mesmo_risco(self):
        self.assertEqual(self.risco(0.3, 0.7, 0.9), self.risco(0.3, 0.7, 0.9))

    def test_duas_instancias_dao_o_mesmo_resultado(self):
        outra = CalculadoraDeRisco()
        self.assertEqual(
            self.risco(0.4, 0.6, 0.8),
            outra.calcular(frequencia=0.4, fraqueza=0.6, exposicao=0.8),
        )


class TestMonotonia(unittest.TestCase):
    """Subir uma entrada não deve reduzir o risco.

    No centroide com regras sobrepostas há quedas pequenas (medidas: no máximo
    0,019 em 0 a 1). O teste aceita até TOLERANCIA e exige monotonia estrita
    nos pontos canônicos 0, 0,5 e 1.
    """

    TOLERANCIA = 0.03

    @classmethod
    def setUpClass(cls):
        cls.calc = CalculadoraDeRisco()

    def risco(self, f: float, w: float, e: float) -> float:
        return self.calc.calcular(frequencia=f, fraqueza=w, exposicao=e)

    def _subidas(self, grade):
        for ponto in itertools.product(grade, repeat=3):
            for eixo in range(3):
                indice = grade.index(ponto[eixo])
                if indice + 1 < len(grade):
                    maior = list(ponto)
                    maior[eixo] = grade[indice + 1]
                    yield ponto, tuple(maior)

    def test_monotonia_estrita_nos_pontos_canonicos(self):
        for menor, maior in self._subidas([0.0, 0.5, 1.0]):
            with self.subTest(menor=menor, maior=maior):
                self.assertGreaterEqual(self.risco(*maior), self.risco(*menor) - 1e-9)

    def test_monotonia_com_tolerancia_numa_grade_mais_fina(self):
        for menor, maior in self._subidas([0.0, 0.2, 0.4, 0.6, 0.8, 1.0]):
            with self.subTest(menor=menor, maior=maior):
                self.assertGreaterEqual(
                    self.risco(*maior), self.risco(*menor) - self.TOLERANCIA
                )


class TestEntradaInvalida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calc = CalculadoraDeRisco()

    def test_valores_invalidos_sao_rejeitados(self):
        invalidos = [-0.1, 1.1, float("nan"), float("inf"), "0.5", None, True]
        for valor in invalidos:
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    self.calc.calcular(frequencia=valor, fraqueza=0.5, exposicao=0.5)

    def test_cada_entrada_e_validada(self):
        for campo in ("frequencia", "fraqueza", "exposicao"):
            entradas = {"frequencia": 0.5, "fraqueza": 0.5, "exposicao": 0.5}
            entradas[campo] = 2.0
            with self.subTest(campo=campo):
                with self.assertRaises(ValueError):
                    self.calc.calcular(**entradas)

    def test_variavel_ou_conjunto_desconhecido_na_pertinencia_e_erro(self):
        with self.assertRaises(ValueError):
            self.calc.grau_de_pertinencia("temperatura", "alta", 0.5)
        with self.assertRaises(ValueError):
            self.calc.grau_de_pertinencia("fraqueza", "enorme", 0.5)


if __name__ == "__main__":
    unittest.main()
