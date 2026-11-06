"""Motor fuzzy do risco de cada aresta (scikit-fuzzy, estilo Mamdani).

Entram frequência, fraqueza e exposição (0 a 1); sai o risco (0 a 1) que o ACO
usa como heurística da aresta. Os conjuntos e as regras ficam em
`fuzzy_config.py`; este módulo só os transforma em um sistema scikit-fuzzy.

Passos do Mamdani, para explicar à banca:
1. fuzzificação: cada entrada recebe um grau de pertinência (baixa/média/alta);
2. regras: E = mínimo, OU = máximo, e o grau da regra "corta" o conjunto de saída;
3. agregação: une os conjuntos de saída cortados (máximo);
4. defuzzificação: o centroide da área resultante vira o número final do risco.
"""

from __future__ import annotations

from math import isfinite

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

from honeyant.pathfinder.dominio.fuzzy_config import (
    CONJUNTOS_ENTRADA,
    CONJUNTOS_SAIDA,
    PONTOS_DO_UNIVERSO,
    REGRAS,
    VARIAVEIS_ENTRADA,
    VARIAVEL_SAIDA,
)


class RiscoIndefinido(RuntimeError):
    """Nenhuma regra disparou. Não deve ocorrer: a tabela cobre todas as entradas."""


def _validar(nome: str, valor: object) -> float:
    if (
        not isinstance(valor, int | float)
        or isinstance(valor, bool)
        or not isfinite(valor)
        or not 0.0 <= valor <= 1.0
    ):
        raise ValueError(f"{nome} deve ser um número finito entre 0 e 1")
    return float(valor)


def _funcao_de_pertinencia(
    tipo: str, universo: np.ndarray, parametros: tuple[float, ...]
) -> np.ndarray:
    if tipo == "trimf":
        return fuzz.trimf(universo, list(parametros))
    return fuzz.trapmf(universo, list(parametros))


class CalculadoraDeRisco:
    """Constrói o sistema fuzzy uma vez e calcula o risco de cada aresta."""

    def __init__(self) -> None:
        universo = np.linspace(0.0, 1.0, PONTOS_DO_UNIVERSO)

        self._entradas: dict[str, ctrl.Antecedent] = {}
        for nome in VARIAVEIS_ENTRADA:
            variavel = ctrl.Antecedent(universo, nome)
            for conjunto, (tipo, parametros) in CONJUNTOS_ENTRADA.items():
                variavel[conjunto] = _funcao_de_pertinencia(
                    tipo, variavel.universe, parametros
                )
            self._entradas[nome] = variavel

        saida = ctrl.Consequent(universo, VARIAVEL_SAIDA)
        for conjunto, (tipo, parametros) in CONJUNTOS_SAIDA.items():
            saida[conjunto] = _funcao_de_pertinencia(tipo, saida.universe, parametros)

        regras = []
        for regra in REGRAS:
            termos = [self._entradas[v][c] for v, c in regra.condicoes]
            antecedente = termos[0]
            for termo in termos[1:]:
                if regra.operador == "AND":
                    antecedente = antecedente & termo
                else:
                    antecedente = antecedente | termo
            regras.append(ctrl.Rule(antecedente, saida[regra.saida]))
        self._sistema = ctrl.ControlSystem(regras)

    def calcular(self, frequencia: float, fraqueza: float, exposicao: float) -> float:
        """Risco de 0 a 1. Entrada fora de 0 a 1 (ou NaN) é erro, nunca é cortada."""
        valores = {
            "frequencia": _validar("frequencia", frequencia),
            "fraqueza": _validar("fraqueza", fraqueza),
            "exposicao": _validar("exposicao", exposicao),
        }
        # Simulação nova a cada chamada: não guarda estado entre cálculos.
        simulacao = ctrl.ControlSystemSimulation(self._sistema)
        for nome, valor in valores.items():
            simulacao.input[nome] = valor
        try:
            simulacao.compute()
        except ValueError as erro:
            raise RiscoIndefinido("nenhuma regra disparou") from erro
        return min(1.0, max(0.0, float(simulacao.output[VARIAVEL_SAIDA])))

    def grau_de_pertinencia(self, variavel: str, conjunto: str, valor: float) -> float:
        """Grau (0 a 1) com que `valor` pertence ao conjunto da variável de entrada."""
        if variavel not in self._entradas:
            raise ValueError("variável de entrada desconhecida")
        if conjunto not in CONJUNTOS_ENTRADA:
            raise ValueError("conjunto desconhecido")
        entrada = self._entradas[variavel]
        grau = fuzz.interp_membership(
            entrada.universe, entrada.terms[conjunto].mf, _validar(variavel, valor)
        )
        return float(grau)
