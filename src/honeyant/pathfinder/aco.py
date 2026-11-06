"""ACO (Ant System clássico) para prever a rota de invasão (spec, seção 9).

Cada iteração:
1. Cada formiga sai da origem e, a cada passo, escolhe a próxima aresta por roleta, com
   chance proporcional a τ^α · η^β (τ = feromônio, η = risco da aresta). Ela não revisita
   nós; se ficar presa num beco sem saída, é descartada.
2. Todo feromônio evapora um pouco (ρ): caminhos não reforçados vão sendo esquecidos.
3. Cada formiga que chegou ao alvo deposita Q / custo em todas as arestas do seu caminho:
   caminhos mais baratos (mais plausíveis) recebem mais feromônio.
4. Os observadores recebem um Snapshot (o domínio não sabe que está sendo desenhado).

O feromônio fica preso entre τ_min e τ_max (ideia do MAX-MIN Ant System) para nenhuma
aresta dominar de vez nem sumir de vez.
"""

import math
import random
from collections.abc import Iterable, Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from honeyant.core.comum import chave_aresta
from honeyant.core.rota import LIMITE_CAMINHOS, Algoritmo, Rota, Snapshot
from honeyant.pathfinder.grafo import ArestaPonderada, GrafoDeRisco
from honeyant.pathfinder.ports import ObservadorDeIteracao


class ParametrosACO(BaseModel):
    """Parâmetros do ACO. Os limites garantem que ele nunca roda para sempre.

    Ajuste medido em 06/11 (100 sementes × 3 grafos: o conhecido dos testes e a casa
    insegura/segura), comparando com o Dijkstra:
    - valores iniciais da spec (β=2, ρ=0,1, τ_max=10): 100 / 100 / 75 acertos;
    - β=1, ρ=0,05, τ_max=1 (padrão abaixo): 100 / 100 / 100, ~10 ms por execução.
    Motivo: na casa segura, as arestas de lan têm risco *local* maior que roteador→broker,
    mas levam a um caminho pior no total. Com β alto a formiga confia demais nesse risco
    local; com τ_max alto o desvio satura e a rota certa deixa de ser sorteada.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    formigas: int = Field(default=20, ge=1, le=1000)
    iteracoes: int = Field(default=50, ge=1, le=1000)
    alfa: float = Field(default=1.0, ge=0, le=10)
    beta: float = Field(default=1.0, ge=0, le=10)
    rho: float = Field(default=0.05, gt=0, lt=1)
    tau0: float = Field(default=0.1, gt=0)
    q: float = Field(default=1.0, gt=0)
    tau_min: float = Field(default=0.01, gt=0)
    tau_max: float = Field(default=1.0, gt=0)
    semente: int = 42

    @model_validator(mode="after")
    def _faixa(self) -> "ParametrosACO":
        if not (self.tau_min <= self.tau0 <= self.tau_max):
            raise ValueError("precisa valer tau_min <= tau0 <= tau_max")
        return self


def evaporar(tau: dict[str, float], rho: float, minimo: float) -> dict[str, float]:
    return {k: max(v * (1 - rho), minimo) for k, v in tau.items()}


def depositar(
    tau: dict[str, float], caminho: Sequence[str], custo: float, q: float, maximo: float
) -> dict[str, float]:
    novo = dict(tau)
    reforco = q / custo  # custo > 0 sempre (custo_da_aresta limita o risco)
    for a, b in zip(caminho, caminho[1:], strict=False):
        k = chave_aresta(a, b)
        novo[k] = min(novo[k] + reforco, maximo)
    return novo


class ACO:
    """Strategy `AlgoritmoDeRota`. Mesma semente → mesma execução (testes e replay)."""

    def __init__(
        self,
        parametros: ParametrosACO | None = None,
        observadores: Iterable[ObservadorDeIteracao] = (),
    ) -> None:
        self.p = parametros or ParametrosACO()
        self._observadores = list(observadores)

    def calcular(self, grafo: GrafoDeRisco, origem: str, alvo: str) -> Rota | None:
        p = self.p
        # Simulação, não criptografia: precisamos de sorteio *reproduzível* pela semente
        # (testes e replay). Nunca o random global.
        rng = random.Random(p.semente)  # noqa: S311  # nosec B311
        execucao_id = UUID(int=rng.getrandbits(128), version=4)
        tau = dict.fromkeys(sorted(grafo.chaves()), p.tau0)
        melhor: tuple[list[str], float] | None = None

        for iteracao in range(p.iteracoes):
            completos: list[tuple[list[str], float]] = []
            for _ in range(p.formigas):
                caminho = self._andar(grafo, tau, origem, alvo, rng)
                if caminho is not None:
                    completos.append((caminho, _custo(grafo, caminho)))

            tau = evaporar(tau, p.rho, p.tau_min)
            for caminho, custo in completos:
                tau = depositar(tau, caminho, custo, p.q, p.tau_max)
                if melhor is None or custo < melhor[1]:
                    melhor = (caminho, custo)

            self._avisar(
                Snapshot(
                    execucao_id=execucao_id,
                    semente=p.semente,
                    iteracao=iteracao,
                    feromonio=tau,
                    caminhos=[c for c, _ in completos[:LIMITE_CAMINHOS]],
                    melhor=_rota(melhor),
                )
            )
        return _rota(melhor)

    def _andar(
        self,
        grafo: GrafoDeRisco,
        tau: dict[str, float],
        origem: str,
        alvo: str,
        rng: random.Random,
    ) -> list[str] | None:
        caminho = [origem]
        visitados = {origem}
        while caminho[-1] != alvo:
            opcoes = [a for a in grafo.saidas(caminho[-1]) if a.destino not in visitados]
            if not opcoes:
                return None  # beco sem saída: formiga descartada
            escolhida = self._roleta(opcoes, tau, rng)
            caminho.append(escolhida.destino)
            visitados.add(escolhida.destino)
        return caminho

    def _roleta(
        self, opcoes: list[ArestaPonderada], tau: dict[str, float], rng: random.Random
    ) -> ArestaPonderada:
        pesos = [tau[a.chave] ** self.p.alfa * a.risco**self.p.beta for a in opcoes]
        total = sum(pesos)
        if total <= 0:  # todas as probabilidades zeradas: escolhe ao acaso, sem dividir por 0
            return rng.choice(opcoes)
        sorteio = rng.random() * total
        for a, peso in zip(opcoes, pesos, strict=True):
            sorteio -= peso
            if sorteio < 0:
                return a
        return opcoes[-1]  # arredondamento de ponto flutuante

    def _avisar(self, snapshot: Snapshot) -> None:
        for o in self._observadores:
            o.notificar(snapshot)


def _custo(grafo: GrafoDeRisco, caminho: Sequence[str]) -> float:
    return sum(grafo.custo(chave_aresta(a, b)) for a, b in zip(caminho, caminho[1:], strict=False))


def _rota(melhor: tuple[list[str], float] | None) -> Rota | None:
    if melhor is None:
        return None
    nos, custo = melhor
    return Rota(nos=nos, custo=custo, plausibilidade=math.exp(-custo), algoritmo=Algoritmo.ACO)
