# ADR pathfinder-01: parâmetros e definições do ACO

- **Status:** PROPOSTO. Os parâmetros do ACO estão como EM ABERTO no contexto do projeto; precisam ser validados pela equipe antes de virarem decisão.
- **Dono:** Kauã (módulo `pathfinder`). **Revisor:** Gustavo.
- **Escopo:** ACO. A tabela fuzzy terá um ADR próprio (`pathfinder-02`).

## Contexto

O ACO prevê a rota de invasão mais provável da internet até a fechadura. O grafo da casa é pequeno (5 a 10 nós), os pesos vêm do fuzzy (risco de 0 a 1) e a mitigação bloqueia ou encarece arestas. O algoritmo é próprio (a banca avalia isso) e precisa ser determinístico, limitado em tempo e explicável.

## Decisões

### Definições

| Item | Decisão | Por quê |
|---|---|---|
| Heurística `η` | `η = max(risco, 0,01)` | usa direto a saída do fuzzy; o piso de 0,01 mantém uma aresta de risco 0 possível, e quem impede passagem é o bloqueio da mitigação |
| Custo da aresta | `custo = 1 − risco` | esforço do atacante; a rota provável é a de menor custo total |
| Custo da rota | soma dos custos das arestas | simples de explicar e de comparar antes/depois |
| Reforço | `q / custo_da_rota` (piso 1e-6) | rota barata reforça mais; o piso evita divisão por zero |
| Anti-ciclo | nó já visitado é proibido | a formiga termina em no máximo `n` passos |
| Beco sem saída | formiga descartada na iteração | não deposita feromônio |

### Parâmetros padrão

| Parâmetro | Valor | Justificativa |
|---|---|---|
| formigas | 20 | grafo pequeno; variedade suficiente sem pesar |
| iterações | 50 (teto 10.000) | converge bem antes; o teto protege contra execução infinita |
| `ρ` (evaporação) | 0,3 | esquece rápido o bastante para o formigueiro mostrar túneis sumindo |
| `α` | 1,0 | feromônio com peso normal |
| `β` | 2,0 | a heurística guia no começo, quando ainda não há feromônio |
| `τ₀` | 1,0 | todas as arestas começam iguais |
| `τmín` / `τmáx` | 0,1 / 10 | nenhuma aresta some de vez nem domina (ideia do Max-Min Ant System) |
| `q` | **0,1** | ver evidência abaixo |

## Evidência: por que `q = 0,1` e não `1,0`

Primeira proposta era `q = 1`. Ao medir, descobrimos que **100% das arestas saturavam em `τmáx`**, o feromônio perdia toda a informação e só a heurística decidia. Medição no grafo "armadilha" dos testes (o primeiro passo mais atraente leva à rota ruim), 30 sementes, 50 iterações:

| Configuração | Formigas na melhor rota (iteração 50) | Arestas saturadas em `τmáx` |
|---|---|---|
| `q = 1` (proposta inicial) | 32% | 100% |
| `q = 0,2` | 56% | 43% |
| **`q = 0,1` (adotado)** | **90%** | 25% |
| `q = 1`, `τmáx = 100` | 91% | 27% |
| `q = 0,2`, `τmáx = 100` | 90% | 0% |

Regra prática (no código): no equilíbrio, o feromônio de uma aresta muito usada tende a `formigas × (q / custo) / ρ`. Se isso passa muito de `τmáx`, tudo bate no teto. Manter `τmáx = 10` e reduzir `q` deixa o teto cumprir seu papel só nas arestas dominantes.

Dois testes de regressão protegem essa decisão: a participação da melhor rota deve crescer ao longo das iterações, e nem todas as arestas podem estar no teto.

## Alternativas descartadas

- **`τmáx = 100`:** funciona, mas deixa o teto sem função prática.
- **Só a melhor formiga deposita:** variante válida (MMAS clássico), mas esconde o "enxame trabalhando" que o formigueiro quer mostrar.
- **Dijkstra:** acharia a mesma rota neste grafo pequeno. O ACO foi escolhido por lidar bem com pesos que mudam com os ataques, por permitir mostrar o algoritmo "pensando" e porque a matéria pede inteligência computacional.
- **Biblioteca pronta de ACO:** escrever o algoritmo é o que a banca avalia.

## Consequências

- Os valores valem para grafos pequenos. Se o grafo da casa crescer muito, rever `q`, formigas e iterações com a regra prática acima.
- Limites de segurança no código: formigas ≤ 1.000, iterações ≤ 10.000, `α` e `β` ≤ 10, limite de tempo opcional com relógio injetado.
- Mesma semente gera a mesma execução, o que permite teste, ensaio e replay.
