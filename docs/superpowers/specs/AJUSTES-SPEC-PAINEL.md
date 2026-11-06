# Ajustes na spec do painel e do formigueiro

> Para o Claude Code. Revise `docs/superpowers/specs/2026-11-06-painel-formigueiro-design.md` com os ajustes abaixo **antes de começar a entrega 1**. Atualize a spec, me mostre o diff do texto e espere minha aprovação.
> Não adicione `Co-Authored-By` nem atribuição ao Claude em commits ou PRs.

---

## 1. Divisão com o Gustavo (decidido: opção B)

- **Você faz o painel inteiro**: servidor (portas, API, stream) e front (cena, página, testes JS), como já está na spec.
- **O Gustavo faz só o login**, num PR separado, em arquivos próprios (`painel/autenticacao.py` e afins). Ele vai precisar de **um único ponto de encaixe** no seu código.
- **Ajuste na spec:** na seção 3, descreva esse ponto de encaixe:
  - a fábrica do app (`criar_app(...)`) recebe as dependências por parâmetro e tem um lugar claro para registrar rotas e uma dependência de proteção (por exemplo, `dependencies=[...]` nos routers da API);
  - todas as rotas `/api/v1/*` e a página principal ficam em routers, para o login proteger tudo de uma vez;
  - nenhum endpoint seu deve depender de "não existir login".
- Mantenha "Login, TLS e o painel na EC2" fora do **seu** escopo, mas troque o texto da seção 2 para "Login: PR do Gustavo, em paralelo, encaixado pela fábrica do app".

## 2. Mitigação: deixar claro que é visual

O edital exige uma vulnerabilidade **real** identificada e mitigada. Essa prova vem do twin (Mosquitto inseguro e seguro, TLS, `.pcap` antes e depois), não do painel.

- O botão passa a se chamar **"Aplicar mitigação (perfil seguro)"**, e a cena mostra uma nota curta: "Simulação do perfil mitigado. A mitigação real e as capturas estão em `docs/capturas/`."
- **Corrija a seção 2:** a frase "Twin: não existe" não é exata. A `twin/planta.py` já existe (planta da casa e tópicos MQTT). Cite-a e confirme que os tipos novos da seção 9 não a quebram (ela ignora tipos que não conhece). Se precisar de ajuste nela, isso é do Kawe e entra em PR dele.

## 3. Ataques reais: usar dados reais, congelados

Sem o `intel`, o cartão "Ataques reais" leria o `resumo-congelado.json`, que é de exemplo. Isso contradiz o diferencial do projeto.

- **Novo comando** em `apps/`: `honeyant-exportar-resumo`. Ele lê o SQLite da isca (em modo somente leitura), agrega numa janela de 24 h e grava um `ResumoDeAmeaca` válido.
  - **Sem IPs** (o contrato já não tem). Aplique o mesmo filtro de IPs da equipe usado pela isca, se existir.
  - Grava em `docs/demo/resumo-real-<data>.json`, com a data e a hora de geração no próprio arquivo.
- O painel usa o resumo real quando existir e cai no de exemplo quando não existir. O cartão mostra a origem: **"Ataques reais, congelados em <data>"** ou **"Dados de exemplo"**.
- Teste: o comando gera um resumo válido a partir de um SQLite de teste e nunca inclui IPs.
- Os números da demo (ver item 9) passam a depender desse resumo: as rotas esperadas da demonstração **têm de continuar as mesmas** com ele. Se não continuarem, me avise antes de calibrar qualquer coisa.

## 4. Proteção contra DNS rebinding

Escutar só em `127.0.0.1` não basta: um site malicioso aberto no mesmo navegador pode apontar um domínio para `127.0.0.1` e ler a API.

- Adicione o `TrustedHostMiddleware` (Starlette, sem dependência nova) aceitando só `127.0.0.1` e `localhost` no modo local. No modo nuvem, o host do painel vem de configuração.
- Teste: requisição com `Host: evil.com` recebe 400.

## 5. Túnel bloqueado: lista explícita

A regra "está no perfil mas não aparece no `feromonio`" é frágil: qualquer outra ausência vira um cadeado falso.

- `AnaliseDeRota` ganha `bloqueadas: list[ChaveDeAresta]`, calculada pelas evidências (mesma regra usada no `montar_grafo`).
- `estadoDoTunel` usa essa lista. O teste JS cobre: aresta bloqueada, aresta ausente do feromônio sem estar bloqueada (não pode virar cadeado) e rota destacada.

## 6. Replay versionado sempre atualizado

- Além do teste do comando, adicione um teste que **regenera em memória** os replays dos dois perfis (semente 42) e compara com os arquivos commitados em `docs/demo/`, no mesmo estilo do teste do JSON Schema. Se as fixtures mudarem, o CI acusa.
- A mensagem do teste diz como regenerar (`uv run honeyant-gravar-replay`).

## 7. Limites explícitos do stream

Troque "regras como hoje" por limites claros:
- `perfil` ∈ {`inseguro`, `seguro`}; `modo` ∈ {`prever`, `replay`};
- `velocidade` ∈ [0,25; 4];
- `semente` inteira entre 0 e 2³¹−1;
- nenhum parâmetro de iterações, formigas ou outros do ACO vindo do cliente;
- no máximo um stream ativo por cliente, e o stream termina sozinho no evento `fim`.

Cada limite tem teste com valor inválido (422).

## 8. Rota do cartão = rota do formigueiro

O cartão usa Dijkstra e a cena usa ACO. Defina na spec que **a fonte da rota exibida é o Dijkstra** (exata) e que a cena mostra a exploração do ACO. Adicione um teste: nos dois perfis, com a semente 42, a melhor rota do último snapshot do ACO é igual à rota do Dijkstra.

## 9. Critério de sucesso sem número cravado

Troque "31× menos plausível" por: "o comparativo mostra a razão de plausibilidade calculada pelo Dijkstra entre os dois perfis". O teste E2E compara a razão exibida com o cálculo, não com um número fixo. O 31× atual pode continuar como exemplo no texto.

## 10. Simplificar o traçado dos túneis (prazo)

O `rotearTunel` com desvio automático é a parte mais arriscada da entrega 1. Troque por:

- **Pontos de controle da curva de cada túnel guardados na fixture**, ajustados uma vez à mão (o layout já é fixo). Se o contrato `PerfilDaCasa` não comporta isso, guarde num arquivo do painel (`static/layout.json` ou um módulo JS), não no `core`.
- O teste de folga continua: **nenhum túnel dos dois perfis passa a menos de `FOLGA` de uma câmara fora dele**. Agora ele verifica os dados.
- O algoritmo automático vira melhoria futura, citada na dívida técnica.

## 11. Ordem de entregas com o caminho crítico

Acrescente na seção 8 uma nota: as entregas 3, 4 e 5 só começam se a prova da vulnerabilidade real (twin + capturas) estiver encaminhada. Se ela estiver atrasada, me avise, porque ela tem prioridade sobre o painel.

---

Depois de atualizar a spec, faça a revisão crítica de sempre (pontos fortes, fracos, riscos, escalabilidade, segurança, melhorias, dívida técnica e notas de 0 a 10) e espere minha aprovação para começar a entrega 0.
