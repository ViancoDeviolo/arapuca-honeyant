# 8. Otimização do Algoritmo ACO e Validação com Dijkstra Gabarito

* Status: Aceito
* Data: 2026-03-30

## Contexto e Problema
O algoritmo de Colônia de Formigas (ACO) precisa encontrar a rota ideal em tempo hábil sem ficar preso em mínimos locais causados pelo risco de arestas intermediárias (como redes LAN).

## Decisão
1. **Parâmetros Finais Otimizados:**
   - Ajuste dos hiperparâmetros da especificação ($\beta=2, \rho=0.1, \tau_{\max}=10$) para $\beta=1, \rho=0.05, \tau_{\max}=1$.
   - Essa alteração aumentou a taxa de convergência da casa segura de 75/100 para 100/100 sementes com tempo médio de execução em torno de 10 ms.
2. **Gabarito com Dijkstra:**
   - Utilização do algoritmo de Dijkstra para validação determinística da rota de menor custo.
3. **Observação de Iterações:**
   - Emissão de instâncias de `Snapshot` da porta `ObservadorDeIteracao` para auditoria e gravação de replay.