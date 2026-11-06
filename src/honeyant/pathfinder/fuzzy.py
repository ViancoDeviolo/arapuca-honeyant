"""Fuzzy de arestas (Mamdani): frequência, fraqueza e exposição → risco (spec, seção 8).

Passo a passo de um cálculo:
1. Fuzzificar: quanto cada entrada pertence a "baixa", "média" e "alta" (0 a 1).
2. Avaliar as regras: "E" = mínimo das pertinências; o resultado é a força da regra.
3. Cortar o conjunto de saída de cada regra na altura da força dela e juntar tudo (máximo).
4. Defuzzificar pelo centroide: o "centro de massa" da área resultante é o risco.
"""

import math

import numpy as np
import skfuzzy as fuzz

RISCO_MIN = 0.001
RISCO_MAX = 0.999

_FRAQUEZA = np.arange(0, 10.01, 0.1)
_RISCO = np.arange(0, 1.0001, 0.001)
_FREQ = np.arange(0, 1.0001, 0.01)

# Funções de pertinência (trapézios nas pontas, triângulo no meio).
# Vizinhos se cruzam de modo que, em todo ponto, baixa + média + alta = 1. Sem isso
# (versão anterior: baixa até 4, alta a partir de 6) havia um trecho em que "média" caía
# sem "alta" subir, e o risco *diminuía* com mais fraqueza: 67 falhas no teste de
# monotonicidade, todas no eixo da fraqueza entre 5 e 6.
_ESCALA_0_10 = {
    "baixa": fuzz.trapmf(_FRAQUEZA, [0, 0, 2, 5]),
    "media": fuzz.trimf(_FRAQUEZA, [2, 5, 8]),
    "alta": fuzz.trapmf(_FRAQUEZA, [5, 8, 10, 10]),
}
_FREQUENCIA = {
    "baixa": fuzz.trapmf(_FREQ, [0, 0, 0.1, 0.3]),
    "media": fuzz.trimf(_FREQ, [0.1, 0.4, 0.7]),
    "alta": fuzz.trapmf(_FREQ, [0.5, 0.8, 1, 1]),
}
_SAIDA = {
    "baixo": fuzz.trapmf(_RISCO, [0, 0, 0.15, 0.3]),
    "medio": fuzz.trimf(_RISCO, [0.2, 0.4, 0.6]),
    "alto": fuzz.trimf(_RISCO, [0.5, 0.7, 0.85]),
    "critico": fuzz.trapmf(_RISCO, [0.75, 0.9, 1, 1]),
}


def _validar(nome: str, valor: float, maximo: float) -> None:
    if not (0 <= valor <= maximo):  # também rejeita NaN
        raise ValueError(f"{nome} fora da faixa [0, {maximo}]: {valor!r}")


class ModeloDeRisco:
    """Sistema fuzzy das arestas. Sem estado: pode ser compartilhado."""

    def risco(self, frequencia: float, fraqueza: float, exposicao: float) -> float:
        _validar("frequencia", frequencia, 1)
        _validar("fraqueza", fraqueza, 10)
        _validar("exposicao", exposicao, 10)

        def grau(conjuntos, universo, valor):
            return {
                termo: float(fuzz.interp_membership(universo, mf, valor))
                for termo, mf in conjuntos.items()
            }

        fq = grau(_FREQUENCIA, _FREQ, frequencia)
        fr = grau(_ESCALA_0_10, _FRAQUEZA, fraqueza)
        ex = grau(_ESCALA_0_10, _FRAQUEZA, exposicao)

        regras = [  # (força, termo de saída) — tabela R1..R8 da spec
            (fr["baixa"], "baixo"),  # R1
            (fr["media"], "medio"),  # R2
            (fr["alta"], "alto"),  # R3
            (min(fr["alta"], ex["alta"]), "critico"),  # R4
            (min(fr["alta"], fq["alta"]), "critico"),  # R5
            (min(fr["media"], fq["alta"]), "alto"),  # R6
            (min(fr["baixa"], ex["alta"], fq["alta"]), "medio"),  # R7
            (min(ex["baixa"], fq["baixa"]), "baixo"),  # R8
        ]
        agregado = np.zeros_like(_RISCO)
        for forca, termo in regras:
            agregado = np.fmax(agregado, np.fmin(forca, _SAIDA[termo]))
        # R1–R3 cobrem toda a faixa de fraqueza, então o agregado nunca é todo zero.
        return float(fuzz.defuzz(_RISCO, agregado, "centroid"))


def custo_da_aresta(risco: float) -> float:
    """Custo = −ln(risco), com o risco limitado para o custo ser sempre positivo e finito."""
    return -math.log(min(max(risco, RISCO_MIN), RISCO_MAX))
