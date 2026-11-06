# Briefing — Redesenho do painel e do Formigueiro 2.5D

> Para o Claude Code. Leia inteiro antes de começar e **planeje antes de codar**.
> Contexto completo do projeto: `docs/superpowers/specs/2026-11-05-arapuca-honeyant-design.md` e `BRAINSTORM.md`.

---

## 0. Antes de tudo

- **Use as skills de design que estiverem disponíveis para você** (frontend, design de interface, crítica e polimento visual, diagramação ou equivalentes). Carregue-as **antes** de desenhar qualquer tela e siga as orientações delas para direção visual, tipografia, cor, layout, movimento e acessibilidade. Se houver mais de uma, use a de direção visual para definir o estilo e a de crítica e polimento para revisar o resultado.
- **Prazo:** último merge de funcionalidade nova em **08/11 às 18h**. Depois disso, só correções e ensaio. Trabalhe em entregas pequenas, cada uma por PR, com o CI verde.
- **Não quebre o que já funciona.** O pathfinder (fuzzy, ACO, Dijkstra, snapshots e replay) está na `main` e testado. O redesenho consome os mesmos dados.
- **Nunca** adicione linhas `Co-Authored-By` ou qualquer atribuição ao Claude em commits e PRs.

## 1. Objetivo

Hoje o painel mostra um grafo genérico: círculos pretos, linhas retas, controles padrão do navegador. A banca precisa **ver a história da demonstração** em poucos segundos:

> Hackers reais atacam a isca → as formigas (ataques e caminhos possíveis) cavam túneis pela casa → o túnel principal chega até a fechadura → aplicamos a mitigação → o túnel desmorona e as formigas são forçadas a um caminho bem pior.

A tela precisa ter **cara de formigueiro visto em corte, com profundidade quase 3D**, e a página inteira precisa ter **visual moderno de produto de segurança**.

## 2. A metáfora (obrigatória)

| Sistema | No formigueiro |
|---|---|
| Internet (origem) | Entrada na superfície, no topo, com o "céu" e a linha do solo |
| Dispositivo | **Câmara** subterrânea: cavidade com profundidade, ícone e nome |
| Fechadura (alvo) | Câmara mais funda, com destaque permanente |
| Aresta do grafo | **Túnel** cavado na terra, curvo e orgânico (nunca uma linha reta) |
| Feromônio | Largura e brilho do túnel: mais feromônio, mais largo e iluminado |
| Evaporação | Túnel pouco usado afina e escurece aos poucos |
| Formiga do ACO | Formiga percorrendo o túnel: caminho possível sendo explorado |
| Ataque real da isca | Formiga de **outra cor** entrando pela superfície quando chega um ataque |
| Rota prevista | Túnel principal contínuo, brilhando na cor de alerta |
| Mitigação | Túnel bloqueado **desmorona**: terra caindo, tracejado, ícone de bloqueio |

### Direção visual "quase 3D" (2.5D)

- Corte do solo em perspectiva leve (isométrica ou oblíqua), com **camadas de terra** em tons diferentes conforme a profundidade, textura sutil e sombras internas nas câmaras e nos túneis para parecerem escavados.
- Câmaras com volume: elipse com sombra interna, borda iluminada e ícone do dispositivo.
- Túneis como caminhos com espessura, sombra e brilho interno. Use curvas, não retas.
- Leve paralaxe ou inclinação ao mover o mouse é bem-vindo, se for sutil e desligado com `prefers-reduced-motion`.
- **Tecnologia:** SVG + CSS + JavaScript puro, como no spec (seção 11). O efeito 3D sai de perspectiva, gradientes, sombras e camadas, não de engine 3D.
  - **Three.js, D3 ou qualquer biblioteca nova** só entram com um ADR curto justificando por que o SVG não resolve, e com versão fixada.
- Animação com `requestAnimationFrame`, no máximo **20 formigas** desenhadas e **um snapshot a cada 150 ms**. Tem que rodar liso num notebook comum.

## 3. Novos dispositivos

### 3.1 Dispositivos IoT conectados ao Wi-Fi

Adicionar à casa: **assistente de voz (tipo Alexa)**, **geladeira inteligente** e, se couber, **smart TV**. Use nomes genéricos ("Assistente de voz", "Geladeira inteligente"), nunca marcas, no código e na tela.

### 3.2 Dispositivos pessoais detectados na rede

Mostrar **notebooks e celulares** da casa como dispositivos **detectados**, visualmente diferentes dos IoT (por exemplo, câmara com contorno tracejado e o selo "detectado").

**Regra de ética e segurança (não negociável):** a detecção acontece **só na rede simulada do Docker**. Nada de varrer a rede real do notebook, da casa ou da faculdade. Isso violaria a política de uso e a LGPD, e na banca pareceria um scanner apontado para a sala. Os notebooks e celulares são **containers simulados**.

Abordagem, da mais simples para a mais completa:

1. **Mínimo (obrigatório se entrar):** os dispositivos pessoais vêm declarados no perfil com o status `detectado`, e o painel os mostra.
2. **Completo (se der tempo):** o módulo `sensor` descobre esses dispositivos de forma **passiva**, observando o tráfego da rede Docker (DHCP, ARP, mDNS ou `client_id` MQTT), e gera evidências. Sem varredura ativa.

### 3.3 Impacto nos outros módulos (planejar antes)

Adicionar dispositivos **muda contratos e fixtures compartilhados**. Antes de codar, faça o levantamento e apresente o plano:

| Onde | O que muda | Dono |
|---|---|---|
| `core/casa.py` | Novos valores em `TipoDeNo` (ou um campo de categoria `iot` / `pessoal` e status `detectado`) | Lucas |
| `docs/demo/perfil-*.json` e `evidencias-*.json` | Novos nós e arestas, com coordenadas para o layout | Lucas |
| `docs/contratos/` | Regenerar o JSON Schema (o CI falha se ficar desatualizado) | Lucas |
| `twin/planta.py` | Hoje aceita exatamente 5 tipos fixos e recusa o resto. Precisa aceitar os novos, ou a casa não sobe | Kawe |
| Testes do `pathfinder` | Rotas esperadas podem mudar com novos nós. A rota da demo tem que continuar passando pela câmera no perfil inseguro | Kauã |

Requisitos:
- **A rota da demonstração não pode mudar:** no perfil inseguro, `internet → câmera → broker → fechadura`; no seguro, a câmera fica bloqueada e a rota passa pelo roteador. Os novos dispositivos entram como caminhos **alternativos** (o assistente de voz e a geladeira são ótimos para mostrar formigas explorando outras rotas), não como atalhos.
- Mudanças no `core` vão num PR próprio, revisado, **antes** do PR do painel.
- Se o prazo apertar, os novos dispositivos podem existir **só no painel e nas fixtures**, sem containers no twin. Declare isso como dívida técnica.

## 4. A página

Visual moderno de produto de segurança: tema escuro, sóbrio, preciso. Sem clichês de "hacker" (letras verdes caindo, caveiras, neon exagerado).

### Layout sugerido (as skills de design podem melhorar)

- **Cabeçalho:** nome do produto, estado da casa como selo grande ("Vulnerável" ou "Protegida") e horário da última atualização da isca.
- **Área principal:** o formigueiro, ocupando a maior parte da tela.
- **Painel lateral:**
  - **Ataques reais (24 h):** total, por serviço (Telnet, MQTT), top senhas tentadas e top países. Dados agregados do `ResumoDeAmeaca`, nunca IPs.
  - **Rota prevista:** os passos em lista, com o ponto fraco destacado.
  - **Comparativo antes e depois:** rota, custo e quanto ficou menos plausível ("rota 6× menos plausível"). Esse é o número que a banca vai lembrar.
  - **Dispositivos na rede:** lista com tipo, status (IoT ou detectado) e nível de risco.
- **Controles:** "Prever invasão", velocidade (0,25× a 4×), **"Aplicar mitigação"** e modo **Replay** (plano B offline). Botões estilizados, com estados de foco, hover e desabilitado.
- **Legenda** clara: o que é túnel, formiga do ACO, formiga de ataque real, rota prevista e túnel bloqueado.

### Problemas da tela atual que precisam sumir

- A rota roteador → broker passa por baixo da lâmpada e parece atravessá-la. Nenhum túnel pode passar sobre uma câmara que não faz parte dele.
- Rótulos sobrepostos às linhas.
- A legenda diz "tracejado", mas a rota aparece contínua.
- `plausibilidade 0.008` sem contexto. Mostre comparação, não número solto.
- Controles com o estilo padrão do navegador.

## 5. Segurança e qualidade (OWASP e regras do projeto)

- Tudo que vem da isca ou das fixtures entra no DOM **só com `textContent`** (ou atributos SVG definidos por código), **nunca `innerHTML`**.
- **CSP sem scripts inline**: CSS e JS em arquivos separados. Fontes e ícones servidos pelo próprio painel (sem CDN em produção) ou explicitamente liberados na CSP.
- O endpoint SSE continua exigindo a mesma autenticação do painel.
- **Acessibilidade:** a cor nunca é o único sinal (use espessura, tracejado, ícone e texto). Contraste adequado no tema escuro. Respeitar `prefers-reduced-motion` (sem animação, a tela mostra o estado final). Controles acessíveis pelo teclado. Um resumo textual da rota acessível a leitores de tela.
- Layout funcionando em 1366×768 (notebook da apresentação) e em projetor.

## 6. Testes

- **Unitários (JS):** conversão de snapshot em estado de desenho (largura do túnel ∝ feromônio, túnel bloqueado, rota destacada), formatação do comparativo antes e depois.
- **Python:** fixtures novas validam no `core`; `twin` aceita os novos tipos; pathfinder mantém as rotas da demo nos dois perfis.
- **Segurança:** dado hostil nas fixtures (nome com `<script>`) aparece como texto, não executa.
- **Visual:** abrir no navegador e conferir os dois perfis, a mitigação e o replay. Tirar prints para o README e para os slides.

## 7. Ordem de entrega (cada item é um PR)

1. **Página e formigueiro 2.5D com os dispositivos atuais.** Maior impacto, menor risco.
2. **Mitigação animada e comparativo antes e depois.**
3. **Painel lateral com os dados da isca.**
4. **Novos dispositivos IoT** (core e fixtures, depois twin, depois painel).
5. **Dispositivos pessoais detectados**, começando pelo mínimo (3.2, item 1).

Se o tempo acabar, o que já foi entregue precisa estar íntegro. Os itens 4 e 5 são os primeiros a cortar.

## 8. Ao terminar cada entrega

Faça a revisão crítica que o projeto exige: pontos fortes, pontos fracos, riscos, escalabilidade, segurança, melhorias futuras, dívida técnica e notas de 0 a 10 para arquitetura, segurança e escalabilidade. Inclua os prints da tela.
