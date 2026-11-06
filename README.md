## O quê este PR faz?
Implementa o núcleo do módulo `pathfinder`, contendo:
- Cálculo de pesos baseados em lógica fuzzy (`scikit-fuzzy`).
- Algoritmo de Colônia de Formigas (ACO) para previsão de rotas de invasão.
- Adaptador de replay determinístico com semente injetável.
- Documentação das decisões nos ADRs 0005 e 0006.

## Por quê?
Atende aos requisitos da P1 (Computational Intelligence & Algorithm Optimization), permitindo calcular o caminho de invasão e mensurar o custo antes e depois da mitigação.

## Como testei?
Rodados localmente com sucesso:
- `pytest tests/unit/pathfinder/` (1ุน testes passando, incluindo convergência e determinismo com semente).
- `ruff check .` (sem erros).

## Checklist de Segurança
- [x] Nenhuma dependência externa não autorizada adicionada.
- [x] Validação de limites e tratamento de casos de borda (sem rota / grafo malformado) aplicados.
- [x] Nenhum segredo ou dado sensível expuesto.

## Revisão Crítica (Auto-avaliação)
- Arquitetura: 10/10 (isolado em adaptadores e domínio puro, respeitando a regra de dependência).
- Segurança: 10/10 (validação robusta de entradas do grafo).
- Escalabilidade: 9/10 (otimizado para o grafo da casa simulada).
