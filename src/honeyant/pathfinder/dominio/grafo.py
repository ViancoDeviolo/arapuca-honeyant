"""Grafo da casa simulada, em versão local e provisória.

PROVISÓRIO: o contrato oficial do grafo vai ficar em `honeyant.core` (definido
pelo Lucas). Esta versão existe para o domínio do ACO ser desenvolvido e
testado agora, sem esperar. Quando o contrato chegar, troca-se só a camada de
entrada; o ACO continua igual.

Convenções:
- arestas são direcionadas;
- `risco` (0 a 1) é a saída do fuzzy: quanto mais alto, mais fácil de invadir;
- `custo = 1 - risco` é o esforço do atacante: a rota mais provável é a de
  menor custo total;
- aresta `bloqueada` (mitigada) nunca é usada.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
from math import isfinite

MAX_NOS = 50
MAX_ARESTAS = 500
# Identificadores só com caracteres seguros: nome vindo de fora nunca vira
# código, caminho de arquivo nem HTML.
_ID_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,32}")


class GrafoInvalido(ValueError):
    """Grafo malformado. Falha cedo, com mensagem clara e sem eco do dado hostil."""


@dataclass(frozen=True)
class Aresta:
    origem: str
    destino: str
    risco: float
    bloqueada: bool = False

    @property
    def chave(self) -> tuple[str, str]:
        return (self.origem, self.destino)

    @property
    def custo(self) -> float:
        return 1.0 - self.risco


def _validar_id(valor: object, campo: str) -> None:
    if not isinstance(valor, str) or _ID_VALIDO.fullmatch(valor) is None:
        raise GrafoInvalido(
            f"{campo}: identificador inválido (1 a 32 letras, dígitos, '_' ou '-')"
        )


def _risco_valido(risco: object) -> bool:
    return (
        isinstance(risco, int | float)
        and not isinstance(risco, bool)
        and isfinite(risco)
        and 0.0 <= risco <= 1.0
    )


class Grafo:
    """Grafo validado e imutável. Se o objeto existe, os dados estão consistentes."""

    def __init__(
        self,
        nos: Iterable[str],
        arestas: Iterable[Aresta],
        origem: str,
        alvo: str,
    ) -> None:
        nos_t = tuple(nos)
        arestas_t = tuple(arestas)

        if not nos_t or len(nos_t) > MAX_NOS:
            raise GrafoInvalido(f"quantidade de nós deve estar entre 1 e {MAX_NOS}")
        if len(arestas_t) > MAX_ARESTAS:
            raise GrafoInvalido(f"máximo de {MAX_ARESTAS} arestas")
        for no in nos_t:
            _validar_id(no, "nó")
        conjunto = set(nos_t)
        if len(conjunto) != len(nos_t):
            raise GrafoInvalido("nós duplicados")

        _validar_id(origem, "origem")
        _validar_id(alvo, "alvo")
        if origem not in conjunto or alvo not in conjunto:
            raise GrafoInvalido("origem e alvo precisam estar entre os nós")
        if origem == alvo:
            raise GrafoInvalido("origem e alvo devem ser diferentes")

        vistas: set[tuple[str, str]] = set()
        for a in arestas_t:
            if not isinstance(a, Aresta):
                raise GrafoInvalido("arestas devem ser do tipo Aresta")
            if a.origem not in conjunto or a.destino not in conjunto:
                raise GrafoInvalido("aresta referencia nó inexistente")
            if a.origem == a.destino:
                raise GrafoInvalido("aresta de um nó para ele mesmo")
            if not _risco_valido(a.risco):
                raise GrafoInvalido("risco deve ser um número finito entre 0 e 1")
            if not isinstance(a.bloqueada, bool):
                raise GrafoInvalido("bloqueada deve ser verdadeiro ou falso")
            if a.chave in vistas:
                raise GrafoInvalido("aresta duplicada")
            vistas.add(a.chave)

        self._nos = nos_t
        self._arestas = arestas_t
        self.origem = origem
        self.alvo = alvo
        self._por_chave = {a.chave: a for a in arestas_t}
        self._saidas: dict[str, tuple[Aresta, ...]] = {
            no: tuple(a for a in arestas_t if a.origem == no and not a.bloqueada)
            for no in nos_t
        }

    @property
    def nos(self) -> tuple[str, ...]:
        return self._nos

    @property
    def arestas(self) -> tuple[Aresta, ...]:
        return self._arestas

    def saidas(self, no: str) -> tuple[Aresta, ...]:
        """Arestas que saem do nó e ainda estão abertas (não mitigadas)."""
        return self._saidas[no]

    def existe_caminho(self) -> bool:
        """Busca em largura: há rota aberta da origem até o alvo?"""
        visitados = {self.origem}
        fila = deque([self.origem])
        while fila:
            no = fila.popleft()
            if no == self.alvo:
                return True
            for a in self._saidas[no]:
                if a.destino not in visitados:
                    visitados.add(a.destino)
                    fila.append(a.destino)
        return False

    def custo_da_rota(self, rota: Iterable[str]) -> float:
        """Soma dos custos das arestas da rota. Rota com aresta bloqueada é erro."""
        nos = tuple(rota)
        total = 0.0
        for origem, destino in zip(nos, nos[1:], strict=False):
            aresta = self._por_chave.get((origem, destino))
            if aresta is None or aresta.bloqueada:
                raise GrafoInvalido("rota usa aresta inexistente ou bloqueada")
            total += aresta.custo
        return total

    def com_bloqueio(self, origem: str, destino: str) -> Grafo:
        """Novo grafo com a aresta bloqueada (modelo de mitigação: segmentação)."""
        if (origem, destino) not in self._por_chave:
            raise GrafoInvalido("aresta a bloquear não existe")
        novas = tuple(
            replace(a, bloqueada=True) if a.chave == (origem, destino) else a
            for a in self._arestas
        )
        return Grafo(self._nos, novas, self.origem, self.alvo)
