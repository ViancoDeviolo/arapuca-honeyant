"""Testes da tabela fuzzy como dados: cobertura das regras e parâmetros coerentes.

Não precisam do scikit-fuzzy: validam a tabela de forma simbólica, nos três
níveis (baixa, média, alta) de cada entrada.
"""

import itertools
import unittest

from honeyant.pathfinder.dominio.fuzzy_config import (
    CONJUNTOS_ENTRADA,
    CONJUNTOS_SAIDA,
    NIVEIS_ENTRADA,
    REGRAS,
    VARIAVEIS_ENTRADA,
)


def regras_que_se_aplicam(niveis: dict[str, str]):
    """Regras que disparam quando cada variável está num nível puro."""
    aplicaveis = []
    for regra in REGRAS:
        casam = [niveis[var] == conj for var, conj in regra.condicoes]
        dispara = all(casam) if regra.operador == "AND" else any(casam)
        if dispara:
            aplicaveis.append(regra)
    return aplicaveis


def todas_as_combinacoes():
    for niveis in itertools.product(NIVEIS_ENTRADA, repeat=len(VARIAVEIS_ENTRADA)):
        yield dict(zip(VARIAVEIS_ENTRADA, niveis, strict=True))


class TestCoberturaDasRegras(unittest.TestCase):
    def test_sao_27_combinacoes_e_todas_tem_pelo_menos_uma_regra(self):
        combinacoes = list(todas_as_combinacoes())
        self.assertEqual(len(combinacoes), 27)
        for niveis in combinacoes:
            with self.subTest(niveis=niveis):
                self.assertGreaterEqual(len(regras_que_se_aplicam(niveis)), 1)

    def test_qualquer_entrada_baixa_so_dispara_a_regra_do_elo_mais_fraco(self):
        for niveis in todas_as_combinacoes():
            if "baixa" not in niveis.values():
                continue
            with self.subTest(niveis=niveis):
                aplicaveis = regras_que_se_aplicam(niveis)
                self.assertEqual(len(aplicaveis), 1)
                self.assertEqual(aplicaveis[0].saida, "baixo")

    def test_sem_nenhuma_baixa_dispara_exatamente_uma_regra(self):
        for niveis in todas_as_combinacoes():
            if "baixa" in niveis.values():
                continue
            with self.subTest(niveis=niveis):
                self.assertEqual(len(regras_que_se_aplicam(niveis)), 1)

    def test_o_risco_cresce_com_a_quantidade_de_entradas_altas(self):
        ordem = {"baixo": 0, "medio": 1, "alto": 2, "muito_alto": 3}
        por_altas: dict[int, set[int]] = {}
        for niveis in todas_as_combinacoes():
            if "baixa" in niveis.values():
                continue
            altas = list(niveis.values()).count("alta")
            saida = regras_que_se_aplicam(niveis)[0].saida
            por_altas.setdefault(altas, set()).add(ordem[saida])
        # cada quantidade de entradas altas tem um único nível de risco
        self.assertTrue(all(len(v) == 1 for v in por_altas.values()))
        niveis_de_risco = [min(por_altas[n]) for n in sorted(por_altas)]
        self.assertEqual(niveis_de_risco, sorted(niveis_de_risco))
        self.assertEqual(min(por_altas[3]), ordem["muito_alto"])

    def test_tres_entradas_altas_dao_muito_alto_e_tres_medias_dao_medio(self):
        todas_altas = dict.fromkeys(VARIAVEIS_ENTRADA, "alta")
        todas_medias = dict.fromkeys(VARIAVEIS_ENTRADA, "media")
        self.assertEqual(regras_que_se_aplicam(todas_altas)[0].saida, "muito_alto")
        self.assertEqual(regras_que_se_aplicam(todas_medias)[0].saida, "medio")


class TestCoerenciaDaConfiguracao(unittest.TestCase):
    def test_regras_so_usam_variaveis_e_conjuntos_que_existem(self):
        for regra in REGRAS:
            with self.subTest(regra=regra.descricao):
                self.assertIn(regra.operador, ("AND", "OR"))
                self.assertIn(regra.saida, CONJUNTOS_SAIDA)
                for var, conj in regra.condicoes:
                    self.assertIn(var, VARIAVEIS_ENTRADA)
                    self.assertIn(conj, CONJUNTOS_ENTRADA)

    def test_toda_regra_tem_descricao_para_explicar_a_banca(self):
        for regra in REGRAS:
            self.assertTrue(regra.descricao.strip())

    def test_parametros_das_funcoes_de_pertinencia_sao_ordenados_e_em_0_1(self):
        todos = {**CONJUNTOS_ENTRADA, **CONJUNTOS_SAIDA}
        for nome, (tipo, parametros) in todos.items():
            with self.subTest(conjunto=nome):
                self.assertIn(tipo, ("trimf", "trapmf"))
                self.assertEqual(len(parametros), 3 if tipo == "trimf" else 4)
                self.assertEqual(list(parametros), sorted(parametros))
                self.assertGreaterEqual(parametros[0], 0.0)
                self.assertLessEqual(parametros[-1], 1.0)

    def test_niveis_de_entrada_batem_com_os_conjuntos(self):
        self.assertEqual(set(NIVEIS_ENTRADA), set(CONJUNTOS_ENTRADA))

    def test_as_tres_variaveis_de_entrada_do_guia(self):
        self.assertEqual(VARIAVEIS_ENTRADA, ("frequencia", "fraqueza", "exposicao"))


if __name__ == "__main__":
    unittest.main()
