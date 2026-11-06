# ADR 0008 — ACO com Dijkstra como gabarito

- **Status:** aceito
- **Data:** 2026-11-06

## Contexto

Com os custos das arestas definidos, o sistema precisa escolher a rota de invasão mais plausível da origem até o alvo. O grafo da casa é pequeno, mas a rota precisa ser estável em testes, determinística por semente e suficientemente rápida para a demo em tempo real.

## Decisão

A implementação adotada foi o algoritmo **ACO (Ant System)** em `src/honeyant/pathfinder/aco.py`, com validação comparativa por **Dijkstra** em `src/honeyant/pathfinder/dijkstra.py`.

- A formiga escolhe a próxima aresta pela roleta, com probabilidade proporcional a `τ^α · η^β`.
- O feromônio evapora globalmente (`ρ`) a cada iteração.
- O melhor caminho reforça as arestas com `Q / custo`, respeitando limites `τ_min` e `τ_max`.
- Cada iteração dispara um `Snapshot` por meio da interface `ObservadorDeIteracao`.
- O sorteio é controlado por `random.Random(semente)`, para que a mesma semente gere a mesma execução.

### Parâmetros finais

| Parâmetro | Valor |
|---|---|
| `formigas` | 20 |
| `iteracoes` | 50 |
| `alfa` | 1 |
| `beta` | 1 |
| `rho` | 0,05 |
| `tau0` | 0,1 |
| `tau_min` | 0,01 |
| `tau_max` | 1 |
| `q` | 1 |
| `semente` | 42 |

Esses valores foram medidos em 100 sementes em 3 grafos: o conhecido dos testes, a casa insegura e a casa segura. A comparação com o Dijkstra mostrou:

| Parâmetros iniciais da spec | Acertos |
|---|---|
| `β=2, ρ=0,1, τ_max=10` | 100 / 100 / 75 |

| Parâmetros finais adotados | Acertos |
|---|---|
| `β=1, ρ=0,05, τ_max=1` | 100 / 100 / 100 |

Com os valores finais, a execução ficou em torno de 10 ms por caso, em média.

## Evidência

O principal problema estava na casa segura: as arestas de LAN tinham risco local aparentemente maior que o trecho roteador→broker, mas levavam ao caminho pior no total. Com `β` alto e `τ_max` alto, o algoritmo confiava demais naquele risco local e saturava as escolhas erradas. Ajustando para `β=1`, `ρ=0,05` e `τ_max=1`, o algoritmo passou a convergir para o gabarito em todas as sementes testadas.

## Por que manter o Dijkstra?

- O Dijkstra continua sendo o gabarito exato para validar a rota.
- O ACO continua sendo útil para visualizar a adaptação do sistema ao longo das iterações e para a demo do formigueiro.
- A combinação de ambos cria um ambiente de teste e de auditoria mais forte do que um único algoritmo isolado.

## Consequências

- O ACO é determinístico quando a semente é fixa, o que facilita replay e regressão.
- Isso também permite segmentar as iterações para debug e para painel de observação.
- Os limites de `formigas` e `iteracoes` ficam protegidos por validação, evitando rodadas excessivamente longas.
