"""Configuração do fuzzy dos pesos, como dados puros (sem scikit-fuzzy).

Separar a tabela do motor deixa as regras fáceis de ler, de explicar à banca e
de testar sem biblioteca. Para mudar uma regra, edite uma linha de `REGRAS`.

Entradas, todas normalizadas de 0 a 1 (a normalização é contrato com o `intel`
e o `twin`, ainda em aberto):
- frequencia: quanto atacam o serviço ligado à aresta;
- fraqueza:   quão fraco é o dispositivo;
- exposicao:  quão alcançável ele é.

Saída: `risco` de 0 a 1. O ACO usa `risco` como heurística (eta) da aresta.

Lógica ("elo mais fraco"): para invadir é preciso os três ao mesmo tempo. Se
qualquer entrada é baixa (sem ataque ativo, dispositivo forte ou fora de
alcance), o risco é baixo. Sem nenhuma baixa, o risco sobe com a quantidade de
entradas altas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VARIAVEIS_ENTRADA = ("frequencia", "fraqueza", "exposicao")
NIVEIS_ENTRADA = ("baixa", "media", "alta")
VARIAVEL_SAIDA = "risco"

# Universo de 0 a 1 com 101 pontos (passo 0,01).
PONTOS_DO_UNIVERSO = 101

# nome -> (tipo, parâmetros). trapmf = [a, b, c, d]; trimf = [a, b, c].
CONJUNTOS_ENTRADA: dict[str, tuple[str, tuple[float, ...]]] = {
    "baixa": ("trapmf", (0.0, 0.0, 0.2, 0.4)),
    "media": ("trimf", (0.2, 0.5, 0.8)),
    "alta": ("trapmf", (0.6, 0.8, 1.0, 1.0)),
}

CONJUNTOS_SAIDA: dict[str, tuple[str, tuple[float, ...]]] = {
    "baixo": ("trapmf", (0.0, 0.0, 0.15, 0.35)),
    "medio": ("trimf", (0.25, 0.45, 0.65)),
    "alto": ("trimf", (0.55, 0.75, 0.9)),
    "muito_alto": ("trapmf", (0.8, 0.92, 1.0, 1.0)),
}


@dataclass(frozen=True)
class Regra:
    operador: Literal["AND", "OR"]
    condicoes: tuple[tuple[str, str], ...]  # (variável, conjunto)
    saida: str
    descricao: str


def _sem_baixa(
    frequencia: str, fraqueza: str, exposicao: str, saida: str, descricao: str
) -> Regra:
    return Regra(
        "AND",
        (
            ("frequencia", frequencia),
            ("fraqueza", fraqueza),
            ("exposicao", exposicao),
        ),
        saida,
        descricao,
    )


REGRAS: tuple[Regra, ...] = (
    Regra(
        "OR",
        (("frequencia", "baixa"), ("fraqueza", "baixa"), ("exposicao", "baixa")),
        "baixo",
        "qualquer entrada baixa: falta um elo para a invasão, risco baixo",
    ),
    _sem_baixa("media", "media", "media", "medio", "as três médias: risco médio"),
    _sem_baixa("alta", "media", "media", "medio", "só a frequência alta: risco médio"),
    _sem_baixa("media", "alta", "media", "medio", "só a fraqueza alta: risco médio"),
    _sem_baixa("media", "media", "alta", "medio", "só a exposição alta: risco médio"),
    _sem_baixa("alta", "alta", "media", "alto", "frequência e fraqueza altas: alto"),
    _sem_baixa("alta", "media", "alta", "alto", "frequência e exposição altas: alto"),
    _sem_baixa("media", "alta", "alta", "alto", "fraqueza e exposição altas: alto"),
    _sem_baixa("alta", "alta", "alta", "muito_alto", "as três altas: muito alto"),
)
