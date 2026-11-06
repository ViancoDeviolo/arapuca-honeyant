# ADR 0006 — ACO para a rota de invasão, com Dijkstra como gabarito

- **Status:** aceito
- **Data:** 2026-11-06
- **Dono:** Kauã (módulo `pathfinder`). **Revisor:** Gustavo.

## Contexto

Com os custos das arestas definidos (ADR 0005), o sistema precisa encontrar a rota de invasão mais plausível da internet até a fechadura e mostrar esse cálculo ao vivo no formigueiro. O grafo da casa é pequeno (8 nós), e o resultado precisa ser determinístico (testes, ensaio e replay) e limitado em tempo.

## Decisão

**ACO (Ant System), implementado pela equipe** (`src/honeyant/pathfinder/aco.py`):

- A formiga escolhe a próxima aresta por roleta, com chance proporcional a τ^α · η^β (τ = feromônio, η = risco da aresta). Não revisita nós; formiga em beco sem saída é descartada.
- Evaporação global ρ a cada iteração; cada formiga que chega ao alvo deposita Q / custo da rota.
- Feromônio preso entre τ_min e τ_max (ideia do MAX-MIN Ant System).
- Sorteio por `random.Random(semente)`: mesma semente, mesma execução.
- Um `Snapshot` por iteração para os observadores (padrão Observer). O gravador de replay (`adapters/replay.py`) é um deles.

**Parâmetros padrão:**

| Parâmetro | Valor |
|---|---|
| formigas | 20 |
| iterações | 50 (teto 1.000) |
| α | 1 |
| β | 1 |
| ρ | 0,05 |
| τ₀ | 0,1 |
| τ_min / τ_max | 0,01 / 1 |
| Q | 1 |
| semente | 42 |

**Dijkstra** (`dijkstra.py`) roda sobre os mesmos custos e dá a rota ótima exata. Os dois implementam a mesma interface `AlgoritmoDeRota` (padrão Strategy), e o Dijkstra serve de gabarito nos testes.

## Evidência

Medição em 06/11 com 100 sementes em 3 grafos (o grafo com armadilhas dos testes, a casa insegura e a casa segura), comparando a rota do ACO com a do Dijkstra:

| Parâmetros | Acertos (conhecido / inseguro / seguro) |
|---|---|
| valores iniciais da spec (β=2, ρ=0,1, τ_max=10) | 100 / 100 / 75 |
| **adotados (β=1, ρ=0,05, τ_max=1)** | **100 / 100 / 100**, cerca de 10 ms por execução |

Motivo da troca: na casa segura, as arestas de LAN têm risco local maior que roteador → broker, mas levam a um caminho pior no total. Com β alto a formiga confia demais nesse risco local; com τ_max alto o desvio satura e a rota certa deixa de ser sorteada.

## Por que ACO, se o Dijkstra resolve?

- O feromônio mostra as rotas alternativas e o quanto cada uma está sendo explorada, não só a melhor.
- O ACO se readapta quando as evidências mudam, sem recomeçar do zero.
- É o que torna o formigueiro possível: a banca vê o algoritmo trabalhando.
- O Dijkstra continua no projeto como prova de que o ACO chega à resposta certa.

## Consequências

- Os valores foram medidos para grafos pequenos. Se a casa crescer muito, refazer a medição.
- Limites no código: formigas ≤ 1.000, iterações ≤ 1.000, α e β ≤ 10.
