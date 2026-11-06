"""Dijkstra: rota ótima exata sobre os custos. Serve de gabarito para o ACO."""

import heapq
import math

from honeyant.core.rota import Algoritmo, Rota
from honeyant.pathfinder.grafo import GrafoDeRisco


class Dijkstra:
    def calcular(self, grafo: GrafoDeRisco, origem: str, alvo: str) -> Rota | None:
        melhor = {origem: 0.0}
        anterior: dict[str, str] = {}
        fila = [(0.0, origem)]
        visitados: set[str] = set()
        while fila:
            custo, no = heapq.heappop(fila)
            if no in visitados:
                continue
            visitados.add(no)
            if no == alvo:
                break
            for a in grafo.saidas(no):
                novo = custo + a.custo
                if novo < melhor.get(a.destino, math.inf):
                    melhor[a.destino] = novo
                    anterior[a.destino] = no
                    heapq.heappush(fila, (novo, a.destino))

        if alvo not in visitados or alvo == origem:
            return None
        nos = [alvo]
        while nos[-1] != origem:
            nos.append(anterior[nos[-1]])
        nos.reverse()
        custo = sum(grafo.custo(f"{a}->{b}") for a, b in zip(nos, nos[1:], strict=False))
        return Rota(
            nos=nos, custo=custo, plausibilidade=math.exp(-custo), algoritmo=Algoritmo.DIJKSTRA
        )
