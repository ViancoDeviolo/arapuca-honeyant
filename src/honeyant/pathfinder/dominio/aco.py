"""ACO (Ant Colony Optimization) próprio: prevê a rota de invasão mais provável.

Ideia em uma frase: formigas virtuais saem da internet e andam até a fechadura
escolhendo cada passo ao acaso, mas com preferência por arestas de risco alto
(heurística) e por arestas que formigas anteriores usaram com sucesso
(feromônio). Rotas baratas (de menor custo) recebem mais feromônio; o feromônio
evapora aos poucos. O enxame converge para a rota mais provável.

Escolha do próximo passo (a partir do nó atual, entre as arestas abertas):

    peso = feromônio^alfa * eta^beta        eta = risco da aresta (do fuzzy)
    probabilidade = peso / soma dos pesos

Fim de cada iteração:

    feromônio = (1 - rho) * feromônio       (evaporação)
    feromônio += q / custo_da_rota          (reforço, para cada formiga que chegou)
    mínimo <= feromônio <= máximo           (nenhuma aresta domina nem some)

Este módulo é domínio puro: sem rede, disco, relógio global nem `random` global.
A aleatoriedade vem de `random.Random(semente)` e o relógio (opcional) é injetado.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from honeyant.pathfinder.dominio.grafo import Grafo
from honeyant.pathfinder.dominio.snapshot import Snapshot

if TYPE_CHECKING:
    from honeyant.pathfinder.ports import ObservadorDeIteracao

Chave = tuple[str, str]
Parada = Literal["concluido", "sem_rota", "tempo_limite", "nao_convergiu"]

# Uma aresta de risco 0 continua possível (eta mínimo) em vez de impossível:
# quem bloqueia caminhos é a mitigação, não o fuzzy.
ETA_MINIMO = 0.01
# Evita dividir por zero quando uma rota tem custo 0 (todas as arestas com risco 1).
CUSTO_MINIMO = 1e-6
_TOLERANCIA = 1e-12

_MAX_FORMIGAS = 1000
_MAX_ITERACOES = 10_000
_MAX_EXPOENTE = 10.0


@dataclass(frozen=True)
class ParametrosACO:
    """Parâmetros do ACO. Os valores padrão são justificados no ADR.

    Regra prática para `q`: no equilíbrio, o feromônio de uma aresta muito usada
    tende a  formigas * (q / custo_da_rota) / rho.  Se isso passar muito de
    `tau_max`, todas as arestas batem no teto e o feromônio deixa de carregar
    informação (o enxame para de aprender). Com 20 formigas e rho 0,3, q = 1
    saturava 100% das arestas; q = 0,1 satura só as melhores.
    """

    formigas: int = 20
    iteracoes: int = 50
    rho: float = 0.3
    alfa: float = 1.0
    beta: float = 2.0
    tau0: float = 1.0
    tau_min: float = 0.1
    tau_max: float = 10.0
    q: float = 0.1
    max_caminhos_snapshot: int = 20

    def __post_init__(self) -> None:
        if not 1 <= self.formigas <= _MAX_FORMIGAS:
            raise ValueError(f"formigas deve estar entre 1 e {_MAX_FORMIGAS}")
        if not 1 <= self.iteracoes <= _MAX_ITERACOES:
            raise ValueError(f"iteracoes deve estar entre 1 e {_MAX_ITERACOES}")
        if not 0.0 < self.rho < 1.0:
            raise ValueError("rho deve estar entre 0 e 1 (exclusivo)")
        if not 0.0 <= self.alfa <= _MAX_EXPOENTE:
            raise ValueError(f"alfa deve estar entre 0 e {_MAX_EXPOENTE}")
        if not 0.0 <= self.beta <= _MAX_EXPOENTE:
            raise ValueError(f"beta deve estar entre 0 e {_MAX_EXPOENTE}")
        if not 0.0 < self.tau_min <= self.tau0 <= self.tau_max:
            raise ValueError("é preciso 0 < tau_min <= tau0 <= tau_max")
        if self.q <= 0.0:
            raise ValueError("q deve ser positivo")
        if not 0 <= self.max_caminhos_snapshot <= _MAX_FORMIGAS:
            raise ValueError("max_caminhos_snapshot fora do intervalo permitido")


@dataclass(frozen=True)
class ResultadoACO:
    """Resultado de uma execução. `rota=None` significa 'sem rota' (não é erro)."""

    rota: tuple[str, ...] | None
    custo: float | None
    iteracoes_executadas: int
    parada: Parada

    @property
    def tem_rota(self) -> bool:
        return self.rota is not None


def evaporar(
    feromonio: Mapping[Chave, float], rho: float, tau_min: float
) -> dict[Chave, float]:
    """Evaporação: todo feromônio perde a fração `rho`, sem passar do mínimo."""
    return {k: max(tau_min, (1.0 - rho) * tau) for k, tau in feromonio.items()}


def depositar(
    feromonio: Mapping[Chave, float],
    rota: Sequence[str],
    quantidade: float,
    tau_max: float,
) -> dict[Chave, float]:
    """Reforço: soma `quantidade` só nas arestas da rota, sem passar do máximo."""
    novo = dict(feromonio)
    for par in zip(rota, rota[1:], strict=False):
        if par in novo:
            novo[par] = min(tau_max, novo[par] + quantidade)
    return novo


def sortear(pesos: Sequence[float], rng: random.Random) -> int:
    """Roleta: devolve o índice sorteado com probabilidade proporcional ao peso.

    Se todos os pesos forem zero (ou a soma não for utilizável), sorteia
    uniformemente em vez de dividir por zero.
    """
    total = sum(pesos)
    if not total > 0.0 or total == float("inf"):
        return rng.randrange(len(pesos))
    ponto = rng.random() * total
    acumulado = 0.0
    for indice, peso in enumerate(pesos):
        acumulado += peso
        if ponto < acumulado:
            return indice
    return len(pesos) - 1


def _construir_caminho(
    grafo: Grafo,
    feromonio: Mapping[Chave, float],
    p: ParametrosACO,
    rng: random.Random,
) -> tuple[str, ...] | None:
    """Uma formiga anda da origem ao alvo. Devolve None se cair em beco sem saída.

    Nós já visitados são proibidos (a formiga não anda em círculos), então o
    caminho termina em no máximo `len(nos)` passos.
    """
    no = grafo.origem
    caminho = [no]
    visitados = {no}
    while no != grafo.alvo:
        opcoes = [a for a in grafo.saidas(no) if a.destino not in visitados]
        if not opcoes:
            return None
        pesos = [
            (feromonio[a.chave] ** p.alfa) * (max(a.risco, ETA_MINIMO) ** p.beta)
            for a in opcoes
        ]
        escolhida = opcoes[sortear(pesos, rng)]
        no = escolhida.destino
        caminho.append(no)
        visitados.add(no)
    return tuple(caminho)


def _tirar_foto(
    iteracao: int,
    feromonio: Mapping[Chave, float],
    caminhos: Sequence[tuple[str, ...]],
    melhor_rota: tuple[str, ...] | None,
    melhor_custo: float | None,
    limite_caminhos: int,
) -> Snapshot:
    return Snapshot(
        iteracao=iteracao,
        feromonio=tuple((o, d, round(tau, 6)) for (o, d), tau in feromonio.items()),
        caminhos=tuple(caminhos[:limite_caminhos]),
        melhor_rota=melhor_rota,
        melhor_custo=None if melhor_custo is None else round(melhor_custo, 6),
    )


def executar(
    grafo: Grafo,
    params: ParametrosACO | None = None,
    semente: int = 0,
    observador: ObservadorDeIteracao | None = None,
    relogio: Callable[[], float] | None = None,
    limite_segundos: float | None = None,
) -> ResultadoACO:
    """Roda o ACO e devolve a melhor rota encontrada.

    - `semente`: mesma semente, mesma execução (teste, ensaio e replay).
    - `observador`: avisado a cada iteração (Observer); o ACO não sabe quem é.
    - `relogio` + `limite_segundos`: limite de tempo; o relógio é injetado para
      o domínio não depender do tempo real (e o teste ser determinístico).
    """
    p = params or ParametrosACO()
    if limite_segundos is not None:
        if relogio is None:
            raise ValueError("limite_segundos exige um relogio injetado")
        if limite_segundos <= 0:
            raise ValueError("limite_segundos deve ser positivo")

    # Sem caminho aberto (ex.: depois da mitigação), é inútil mandar formigas.
    if not grafo.existe_caminho():
        return ResultadoACO(None, None, 0, "sem_rota")

    rng = random.Random(semente)  # nosec B311
    feromonio: dict[Chave, float] = {
        a.chave: p.tau0 for a in grafo.arestas if not a.bloqueada
    }
    melhor_rota: tuple[str, ...] | None = None
    melhor_custo: float | None = None
    inicio = relogio() if relogio is not None else 0.0
    executadas = 0
    parada: Parada = "concluido"

    for iteracao in range(1, p.iteracoes + 1):
        if (
            relogio is not None
            and limite_segundos is not None
            and relogio() - inicio >= limite_segundos
        ):
            parada = "tempo_limite"
            break

        caminhos: list[tuple[str, ...]] = []
        for _ in range(p.formigas):
            caminho = _construir_caminho(grafo, feromonio, p, rng)
            if caminho is not None:  # formiga em beco sem saída é descartada
                caminhos.append(caminho)

        feromonio = evaporar(feromonio, p.rho, p.tau_min)
        for caminho in caminhos:
            custo = grafo.custo_da_rota(caminho)
            quantidade = p.q / max(custo, CUSTO_MINIMO)
            feromonio = depositar(feromonio, caminho, quantidade, p.tau_max)
            if melhor_custo is None or custo < melhor_custo - _TOLERANCIA:
                melhor_rota, melhor_custo = caminho, custo

        executadas = iteracao
        if observador is not None:
            observador.ao_iterar(
                _tirar_foto(
                    iteracao,
                    feromonio,
                    caminhos,
                    melhor_rota,
                    melhor_custo,
                    p.max_caminhos_snapshot,
                )
            )

    if melhor_rota is None and parada == "concluido":
        parada = "nao_convergiu"
    return ResultadoACO(melhor_rota, melhor_custo, executadas, parada)
