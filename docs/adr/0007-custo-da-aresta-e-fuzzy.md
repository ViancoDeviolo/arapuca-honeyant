# 7. Custo da Aresta e Lógica Fuzzy para Avaliação de Risco

* Status: Aceito
* Data: 2026-03-30

## Contexto e Problema
O módulo *Pathfinder* precisa calcular o custo de cada aresta do mapa com base nos níveis de fraqueza/risco detectados. A inferência fuzzy Mamdani é utilizada para mapear os pontos da tabela da especificação (+4, +3, +2, +1) em um valor numérico de risco.

## Decisão
1. **Modelagem Fuzzy (Mamdani):**
   - Utilização de regras R1–R8 com desfuzzificação por centroide.
   - O que não for observado conta como o pior caso de fraqueza.
2. **Métrica de Custo:**
   - O custo de deslocamento de cada aresta é formalizado como `custo = -ln(risco)`.
3. **Ajuste de Monotonicidade:**
   - Reajuste das funções de pertinência originais (cruzamento dos conjuntos difusos) para eliminar inconsistências onde um aumento de fraqueza gerava menor risco estimado (falhas zeradas nos 67 pontos da grade 11×11×11).