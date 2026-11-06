# ADR 0007 — Custo da aresta e lógica fuzzy para avaliação de risco

- **Status:** aceito
- **Data:** 2026-11-06

## Contexto

O `pathfinder` precisa transformar a evidência da casa em um peso por aresta. Esse peso precisa refletir três dimensões ao mesmo tempo: a frequência com que o serviço é atacado, a fraqueza da conexão e a exposição do trecho no perfil da casa. A decisão de projeto também precisa ser simples de explicar e robusta para testes determinísticos.

## Decisão

A solução adotada foi um sistema **fuzzy Mamdani** em `src/honeyant/pathfinder/fuzzy.py`, usando os três inputs da spec:

| Entrada | Faixa | Origem |
|---|---|---|
| `frequencia` | 0 a 1 | `ResumoDeAmeaca` |
| `fraqueza` | 0 a 10 | pontos da aresta (+4 credencial vazada, +3 texto puro, +2 sem autenticação, +1 sem ACL) |
| `exposicao` | 0 a 10 | perfil da casa |

- As variáveis têm termos baixa, média e alta.
- A saída `risco` usa os termos baixo, médio, alto e crítico.
- Regras R1–R8 da spec: `E = mínimo`, agregação por `máximo`, defuzzificação por centroide.
- O custo da aresta é definido como `−ln(risco)`, com risco limitado ao intervalo `[0.001, 0.999]` para manter custo finito e sempre positivo.

Essa definição é matemática: somar `−ln(risco)` ao longo da rota equivale a multiplicar os riscos dos trechos. A rota de menor custo é a rota de maior plausibilidade, e a plausibilidade da rota final é `e^(-custo)`.

## Evidência

- **Monotonicidade:** a primeira versão das funções de pertinência tinha um buraco em fraqueza entre 5 e 6. Como os conjuntos "média" e "alta" não cruzavam direito, o risco caía mesmo com a fraqueza aumentando; a grade 11×11×11 falhava em 67 pontos.
- **Correção aplicada:** os conjuntos foram ajustados para cruzarem sem deformar a área total, de modo que, em toda faixa, baixa + média + alta continua somando 1. Isso eliminou as falhas e deixou o risco monotônico no eixo da fraqueza.
- **Risco como score comparativo:** o valor do risco não é uma probabilidade calibrada; o centroide nunca chega exatamente a 0 nem 1, e isso é esperado para comparação entre rotas.

## Alternativas descartadas

- **Custo = 1 − risco:** simples, mas sem correspondência matemática com a combinação dos passos; não compara rotas de tamanhos diferentes de forma consistente.
- **Somar pontuação bruta de fraqueza sem fuzzy:** ignora frequência e exposição; não atende ao requisito de inferência fuzzy.
- **Defuzzificação por média dos máximos:** produz passos discretos e piora a suavidade que o ACO precisa para explorar heurísticas contínuas.

## Consequências

- O módulo `fuzzy.py` é o único lugar da regra de risco; qualquer mudança de termos ou regras reflete diretamente no custo das arestas.
- A correção de monotonicidade passou a ser reforçada por testes automatizados, preservando a propriedade quando o modelo evolui.
- Dependências do fuzzy continuam no extra `inteligencia` do `pyproject.toml`, mantendo o restante da aplicação leve.
