# ADR pathfinder-02: fuzzy dos pesos (risco da aresta)

- **Status:** PROPOSTO. Variáveis e regras fuzzy estão como EM ABERTO no contexto do projeto; precisam ser validadas pela equipe.
- **Dono:** Kauã (módulo `pathfinder`). **Revisor:** Gustavo.

## Contexto

O ACO precisa de um peso (heurística) para cada aresta do grafo da casa. Esse peso deve refletir o que os atacantes estão fazendo agora e o quanto cada dispositivo é fraco e alcançável. A matéria pede lógica fuzzy calculando risco.

## Decisão

**Entradas** (normalizadas de 0 a 1, três conjuntos cada: baixa, média, alta):

| Entrada | Significado | Vem de |
|---|---|---|
| `frequencia` | quanto atacam o serviço ligado à aresta | `intel` (resumo) |
| `fraqueza` | quão fraco é o dispositivo | `twin` |
| `exposicao` | quão alcançável ele é | `twin` |

**Saída:** `risco` de 0 a 1, com quatro conjuntos: baixo, médio, alto, muito alto.

**Funções de pertinência** (parâmetros em `fuzzy_config.py`):

| Conjunto | Forma | Parâmetros |
|---|---|---|
| entrada baixa | trapezoidal | 0, 0, 0,2, 0,4 |
| entrada média | triangular | 0,2, 0,5, 0,8 |
| entrada alta | trapezoidal | 0,6, 0,8, 1, 1 |
| risco baixo | trapezoidal | 0, 0, 0,15, 0,35 |
| risco médio | triangular | 0,25, 0,45, 0,65 |
| risco alto | triangular | 0,55, 0,75, 0,9 |
| risco muito alto | trapezoidal | 0,8, 0,92, 1, 1 |

**Regras (lógica do "elo mais fraco"):** para invadir é preciso os três ao mesmo tempo.

| # | Se | Então risco |
|---|---|---|
| 1 | qualquer entrada é baixa | baixo |
| 2 | as três são médias | médio |
| 3 a 5 | nenhuma baixa e **uma** alta | médio |
| 6 a 8 | nenhuma baixa e **duas** altas | alto |
| 9 | as três altas | muito alto |

A regra 1 cobre as 19 combinações com alguma entrada baixa. As regras 2 a 9 cobrem as 8 combinações de média e alta. Juntas cobrem as 27 combinações, sem lacuna (um teste simbólico garante isso, porque o scikit-fuzzy falha quando nenhuma regra dispara).

**Motor:** scikit-fuzzy, Mamdani: E = mínimo, OU = máximo, agregação por máximo, defuzzificação por centroide, universo de 0 a 1 com 101 pontos.

## Evidência e limitação conhecida

Valores de referência de uma implementação independente (mínimo/máximo e centroide), usados nos testes:

| Entradas (freq, fraq, expo) | Risco |
|---|---|
| 0, 0, 0 | 0,129 |
| 0,5, 0,5, 0,5 | 0,450 |
| 1, 1, 0,5 | 0,733 |
| 1, 1, 1 | 0,928 |
| qualquer uma em 0 e as outras em 1 | 0,129 |

**Monotonia:** subir uma entrada não deveria reduzir o risco. Numa grade de passo 0,1 (3.630 comparações), 45 (1,2%) apresentam queda, **no máximo de 0,019** (de 0 a 1). Isso é um efeito conhecido do centroide quando as regras se sobrepõem, não um erro de lógica. Nos pontos canônicos (0, 0,5 e 1) a monotonia é estrita. Os testes exigem monotonia estrita nos pontos canônicos e aceitam queda de até 0,03 numa grade mais fina.

## Alternativas descartadas

- **Somar os níveis das entradas:** mais simples de codificar, mas diz que um dispositivo forte compensa um fraco, o que não faz sentido para invasão.
- **Regras só com E, sem a regra do elo mais fraco:** exigiria 27 regras escritas à mão, difíceis de explicar.
- **Outros métodos de defuzzificação (ex.: média dos máximos):** não foram medidos. O centroide é o padrão do scikit-fuzzy e dá risco contínuo, que é o que o ACO usa como heurística.

## Dependências (versões fixadas, aprovar com o Lucas)

`scikit-fuzzy==0.5.0`, `numpy==2.5.4`, `scipy==1.18.1`, `networkx==3.7`. O scikit-fuzzy não instala numpy, scipy nem networkx sozinho, por isso as três entram explicitamente.

## Consequências

- Mudar uma regra é editar uma linha de `REGRAS`; os testes simbólicos acusam lacuna ou conflito.
- A normalização das entradas (0 a 1) e o mapeamento de serviço para aresta dependem do contrato do `core` (pendente com o Lucas e o Rafael).
