# ADR 0005 — Risco da aresta por lógica fuzzy e custo como −ln(risco)

- **Status:** aceito
- **Data:** 2026-11-06
- **Dono:** Kauã (módulo `pathfinder`). **Revisor:** Gustavo.

## Contexto

O pathfinder precisa de um peso para cada ligação (aresta) entre dispositivos da casa. Esse peso tem de refletir três coisas ao mesmo tempo: o quanto os atacantes reais estão mirando aquele serviço agora (vem da isca), o quanto a ligação é fraca (credencial vazada, texto puro, sem autenticação, sem ACL) e o quanto ela está exposta. A matéria de Inteligência Computacional pede uma técnica de IC com função real no sistema.

## Decisão

**Fuzzy Mamdani** (`src/honeyant/pathfinder/fuzzy.py`, scikit-fuzzy):

| Entrada | Faixa | Origem |
|---|---|---|
| `frequencia` | 0 a 1 | `ResumoDeAmeaca`: ataques ao serviço da aresta ÷ total de eventos |
| `fraqueza` | 0 a 10 | evidências da aresta (+4 credencial vazada, +3 texto puro, +2 sem autenticação, +1 sem ACL) |
| `exposicao` | 0 a 10 | atributo da aresta no `PerfilDaCasa` |

- Cada entrada tem os termos baixa, média e alta; a saída `risco` tem baixo, médio, alto e crítico.
- Regras R1 a R8 da spec (seção 8). R1 a R3 dependem só da fraqueza e cobrem toda a faixa, então toda entrada dispara ao menos uma regra.
- E = mínimo, agregação = máximo, defuzzificação por centroide.

**Custo da aresta = −ln(risco)**, com o risco limitado a [0,001; 0,999] para o custo ser sempre positivo e finito.

O motivo é matemático: somar −ln(risco) ao longo da rota equivale a multiplicar os riscos. A rota de menor custo é a de maior produto de riscos, ou seja, aquela em que *todos os passos* têm mais chance de dar certo ao mesmo tempo. A `plausibilidade` da rota é e^(−custo).

## Evidência

- **Monotonicidade:** aumentar qualquer entrada nunca pode reduzir o risco. A primeira versão das funções de pertinência (fraqueza "baixa" até 4 e "alta" a partir de 6) falhava em 67 pontos da grade 11×11×11, todos com fraqueza entre 5 e 6: naquele trecho "média" caía sem "alta" subir. As funções foram refeitas para que, em todo ponto, baixa + média + alta = 1. O teste `test_monotonicidade_na_grade_11x11x11` protege isso.
- O "risco" é um score para comparar rotas, não uma probabilidade calibrada. O centroide nunca chega a 0 nem a 1, e isso é esperado.

## Alternativas descartadas

- **Custo = 1 − risco:** mais simples, mas somar (1 − risco) não corresponde a nenhuma combinação dos riscos dos passos; a comparação entre rotas de tamanhos diferentes fica sem significado.
- **Somar os pontos de fraqueza sem fuzzy:** não combina frequência e exposição, e não atende ao requisito de IC.
- **Outras defuzzificações (média dos máximos):** dão saída em degraus; o ACO precisa de um risco contínuo como heurística.

## Consequências

- Mudar uma regra é editar uma linha da lista `regras`; o teste de monotonicidade acusa se a mudança quebrar a propriedade.
- Dependências do fuzzy (`numpy`, `scikit-fuzzy`, `scipy`) ficam no extra opcional `inteligencia` do `pyproject.toml`, para a imagem da isca não carregá-las.

## Sensibilidade medida (09/11)

Na auditoria final, a pergunta foi: quanto a frequência de ataques vinda da isca muda a rota
prevista *nesta* casa? A resposta foi medida com Dijkstra sobre `montar_grafo`, usando as
fixtures de `docs/demo`, e está travada em
[`tests/e2e/test_sensibilidade_a_isca.py`](../../tests/e2e/test_sensibilidade_a_isca.py).

| Resumo usado | Rota do perfil inseguro | Plausibilidade | Rota do perfil seguro |
|---|---|---|---|
| zero ataques (`total_eventos` = 0) | internet → câmera → broker → fechadura | 0,2412 | internet → roteador → broker → fechadura |
| congelado (82% Telnet) | internet → câmera → broker → fechadura | 0,2412 | internet → roteador → broker → fechadura |
| real de 07/11 (98% Telnet) | internet → câmera → broker → fechadura | 0,2412 | internet → roteador → broker → fechadura |
| 50% Telnet, 50% MQTT | internet → câmera → broker → fechadura | 0,2921 | internet → roteador → broker → fechadura |
| 100% MQTT | internet → câmera → broker → fechadura | 0,3726 | internet → roteador → broker → fechadura |

O risco de `internet->camera` (fraqueza 8, exposição 9) é 0,795 com frequência 0; 0,25; 0,5;
0,75 e 1: a aresta já está saturada. O custo do perfil seguro é 4,86 em todos os casos.

**Por quê:** nesta casa, a fraqueza e a exposição já saturam o risco das arestas da rota.
As regras que usam a frequência só mudam o resultado quando ela chega perto de 50% dos
ataques num serviço ou passa disso (o termo "alta" começa em 0,5; com 18% de MQTT, como no
resumo congelado, o risco é o mesmo de zero ataques). Por isso a isca altera a plausibilidade (de 0,24 para 0,37 se o
MQTT dominar), não a rota. Hoje o Telnet domina os ataques reais, e as arestas MQTT da rota
ficam com o risco que a fraqueza delas dá.

**Credenciais:** a credencial "vazada" que pesa na fraqueza de `camera->broker` vem da lista
estática de padrões de fábrica (`core/credenciais.py`), porque a isca ainda não capturou
nenhum par completo de usuário e senha ([`docs/demo/LEIAME.md`](../demo/LEIAME.md)).

**Consequência:** numa casa maior, ou com fraquezas parecidas entre caminhos, a frequência
passa a decidir o empate e a isca muda a rota. Melhoria futura: recalibrar as funções de
pertinência da frequência para ela pesar também abaixo de 50%. Isso muda os custos da demo,
então exige medir de novo e atualizar esta tabela e os replays.
