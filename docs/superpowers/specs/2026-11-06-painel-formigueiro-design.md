# Painel e Formigueiro em grade: design (spec)

- **Data:** 2026-11-06
- **Status:** aprovado em conversa (abordagem A + seções 1 a 3); revisado com `AJUSTES-SPEC-PAINEL.md`. Em 07/11 a direção visual mudou: a cena 2.5D (câmaras ovais e túneis curvos) foi substituída pela rede em grade ortogonal da seção 4; aguardando aprovação dessa mudança
- **Origem:** `docs/superpowers/BRIEFING-PAINEL-FORMIGUEIRO.md` e `docs/superpowers/specs/AJUSTES-SPEC-PAINEL.md`
- **Spec-mãe:** `docs/superpowers/specs/2026-11-05-arapuca-honeyant-design.md` (seções 3, 6, 11, 12 e 13 continuam valendo; onde este documento for mais específico, ele prevalece para o painel)
- **Base de código:** a branch `feat/esqueleto-local` (painel mínimo: FastAPI + SSE + SVG simples). Ela entra na `main` antes de qualquer entrega daqui.

---

## 1. Objetivo e critério de sucesso

Em poucos segundos, a banca precisa **ver a história da demonstração**:

> Hackers reais atacam a isca → formigas cavam túneis pela casa → o túnel principal chega à fechadura → aplicamos a mitigação → o túnel desmorona e as formigas são forçadas a um caminho bem pior.

**Pronto quando:**
1. a página abre em 1366×768 e no projetor com o formigueiro em grade (seção 4);
2. "Prever invasão" mostra a rota `internet → câmera → broker → fechadura`;
3. "Aplicar mitigação (perfil seguro)" desmorona o túnel câmera→broker, a rota passa pelo roteador e o comparativo mostra **a razão de plausibilidade calculada pelo Dijkstra entre os dois perfis**. Com as fixtures atuais ela dá cerca de 31×, mas o número só serve de exemplo: o teste compara o valor exibido com o cálculo, não com uma constante;
4. "Replay" faz o mesmo sem rodar o ACO;
5. todos os testes desta spec estão verdes no CI.

## 2. Decisões tomadas

| Pergunta | Decisão |
|---|---|
| O que o botão "Aplicar mitigação (perfil seguro)" faz | **É visual: troca o perfil no painel** (inseguro → seguro) e roda o stream de novo. Não chama o `honeyant mitigar`. A cena mostra a nota: "Simulação do perfil mitigado. A mitigação real e as capturas estão em `docs/capturas/`." A prova da vulnerabilidade real, exigida pelo edital, vem do twin (Mosquitto inseguro e seguro, TLS, `.pcap` antes e depois), não do painel. "Desfazer" volta, para repetir a demo. |
| Login no painel | **PR do Gustavo, em paralelo**, em arquivos próprios (`painel/autenticacao.py` e afins), encaixado pela fábrica do app (seção 3.5). Esta spec não implementa login, TLS nem o painel na EC2, mas nenhum endpoint daqui depende de "não existir login". Até o login entrar, o painel continua recusando hosts fora do loopback. |
| Twin | O briefing cita a `twin/planta.py` do Kawe (planta da casa e tópicos MQTT). **Em 06/11 às 20h ela ainda não está no GitHub** (nenhuma branch), então não foi possível conferir. Requisito: ela precisa ignorar os tipos de nó que não conhece, para os tipos novos da seção 9 não a quebrarem. Qualquer ajuste nela é do Kawe e entra em PR dele. Os dispositivos novos entram no `core`, nas fixtures e no painel; os containers deles no twin são dívida técnica. |
| Abordagem técnica | **A:** desenho calculado no navegador, com JS em módulos pequenos e funções puras testadas com `node --test`. SVG + CSS + JS puro, sem bibliotecas novas. |

## 3. Arquitetura e dados

### 3.1 Responsabilidades

- `painel/` importa só o `core` (regra do import-linter). Ele recebe os dados por portas.
- `apps/local.py` é o único que lê arquivos e roda o pathfinder. Ele implementa as portas.

### 3.2 Portas (`painel/ports.py`)

```python
class FonteDoFormigueiro(Protocol):
    def snapshots(self, perfil: TipoDePerfil, semente: int) -> Sequence[Snapshot]: ...
    def replay(self, perfil: TipoDePerfil) -> Sequence[Snapshot] | None: ...   # None = sem arquivo
    def analise(self, perfil: TipoDePerfil) -> AnaliseDeRota: ...              # Dijkstra (exata)

class FonteDoResumo(Protocol):
    def resumo(self) -> ResumoComOrigem: ...
```

`ResumoComOrigem` (modelo do painel) = `{origem: "real" | "exemplo", resumo: ResumoDeAmeaca}`. A data exibida é o `resumo.gerado_em`.

`AnaliseDeRota` é um modelo pydantic **do painel**, não um contrato do `core`. Campos:
- `rota: Rota | None`: a rota do **Dijkstra**;
- `riscos: dict[ChaveDeAresta, float]`, com o risco fuzzy das arestas **da rota**;
- `riscos_por_no: dict[IdDeNo, float]`, com o maior risco entre as arestas que tocam cada nó, para a lista de dispositivos;
- `bloqueadas: list[ChaveDeAresta]`, com as arestas do perfil bloqueadas pelas evidências. A regra é a mesma do `montar_grafo` (`pathfinder.fraqueza.bloqueada`), calculada em `apps/`.

**Qual rota é a oficial:** a rota exibida no cartão, no texto acessível e no comparativo é a do **Dijkstra** (exata). A cena mostra a **exploração** do ACO. Um teste garante que, nos dois perfis e com a semente 42, a melhor rota do último snapshot do ACO é igual à do Dijkstra.

### 3.3 API (só GET, JSON)

| Rota | Resposta |
|---|---|
| `GET /api/v1/casa?perfil=inseguro\|seguro` | `PerfilDaCasa` |
| `GET /api/v1/resumo` | `ResumoComOrigem` (agregado; o contrato não tem IPs) |
| `GET /api/v1/rotas` | `{"inseguro": AnaliseDeRota, "seguro": AnaliseDeRota}` |
| `GET /api/v1/formigueiro/stream?perfil=&modo=prever\|replay&semente=42&velocidade=1` | Eventos `snapshot` e `fim` (limites na seção 3.4) |
| `GET /api/v1/replay` | `{"inseguro": bool, "seguro": bool}`: existe arquivo de replay para aquele perfil? |

- O `GET /api/v1/perfil` atual é **substituído** por `/api/v1/casa`.
- `perfil` inválido gera 422.
- `modo=replay` sem arquivo gera 404, com uma mensagem curta e sem stack trace.

### 3.4 Limites do stream

| Parâmetro | Aceito | Fora disso |
|---|---|---|
| `perfil` | `inseguro`, `seguro` | 422 |
| `modo` | `prever`, `replay` | 422 |
| `velocidade` | número em [0,25; 4] (sem NaN nem infinito) | 422 |
| `semente` | inteiro em [0; 2³¹−1] | 422 |
| qualquer outro parâmetro (iterações, formigas, α, β…) | não existe: o ACO usa só `ParametrosACO` do servidor | ignorado; nenhum parâmetro do ACO vem do cliente |

- **Um stream ativo por cliente** (identificado pelo IP de origem): quando o mesmo cliente abre um stream novo, o anterior é encerrado com o evento `fim`. A regra é "o mais novo vence" e não "recusar o segundo", porque, ao clicar de novo, o navegador abre o novo stream antes de o servidor perceber que o antigo foi fechado.
- **Fim do stream:** ele termina sozinho no evento `fim`, depois do último snapshot.
- **Espaçamento:** no máximo um snapshot a cada 150 ms (`max(0,15, 0,6 / velocidade)` s).
- **Testes:** cada linha da tabela tem teste com valor inválido (422), e há um teste para "o mais novo vence".

### 3.5 Ponto de encaixe do login (Gustavo)

- **Fábrica:** `criar_app(..., encaixe: Encaixe = Encaixe())`. O `Encaixe` tem `protecao_api`, `protecao_pagina` e `routers`. São duas proteções porque a API responde 401 e a página redireciona (303) para `/login`.
- **Routers:** as rotas ficam em dois `APIRouter`: o `api` (`/api/v1/*`, com `protecao_api`) e o `pagina` (`/`, com `protecao_pagina`).
- **Estáticos públicos:** `/static/*` é montado com `StaticFiles`, que não aceita dependências. Ele fica público, porque é o mesmo código que está no GitHub, sem dado nenhum. Os dados só saem pela API, que é protegida.
- **Rotas do próprio login:** os `routers` do encaixe entram sem proteção, antes dos outros. O PR do Gustavo cria `apps/painel_login.py` com `encaixe_do_ambiente() -> Encaixe` (lê o ambiente e falha na partida se a configuração estiver inválida). Em `apps/local.py`, ele muda uma linha: `montar(config, encaixe=encaixe_do_ambiente())`.
- **Sem dependência implícita:** nenhum endpoint daqui assume que não há login. O JS trata 401 e 403 com "Sessão expirada. Entre de novo.", sem quebrar a cena. O stream usa o mesmo cookie (o `EventSource` envia cookies da mesma origem).
- **Cookie `Secure`:** o navegador aceita cookie `Secure` em `http://127.0.0.1` e `http://localhost`, porque trata os dois como contexto seguro. Isso precisa ser conferido no navegador da demo. O painel não é exposto em HTTP puro na EC2. Se um dia rodar lá, o acesso é por túnel SSH (`ssh -L`), que chega pelo `127.0.0.1` local.
- **Teste do encaixe:** proteções falsas fazem todas as rotas `/api/v1/*` responderem 401 e a página responder 303 para `/login`. Os `routers` do encaixe continuam abertos.

### 3.6 Fluxo da mitigação (só no front, visual)

1. **Estado inicial:** `perfil = inseguro` e selo "Vulnerável".
2. **"Aplicar mitigação (perfil seguro)":** animação de desmoronamento do túnel câmera→broker (seção 4.6); `perfil = seguro`; um novo stream; selo "Protegida"; a nota "Simulação do perfil mitigado. A mitigação real e as capturas estão em `docs/capturas/`."; o botão vira "Desfazer mitigação".
3. **"Desfazer":** volta ao estado inicial. Nada muda no servidor.

### 3.7 Ataques reais, congelados

Sem o `intel`, o cartão leria o `resumo-congelado.json`, que é **de exemplo**. Isso contradiz o diferencial do projeto. Então:

- **Novo comando `honeyant-exportar-resumo`** (em `apps/`):
  - **Leitura:** abre o SQLite da isca com o `LeitorSqlite` (`mode=ro`) e agrega os eventos de uma janela de 24 h num `ResumoDeAmeaca` válido, com `gerado_em` = data e hora da geração.
  - **Saída:** grava em `docs/demo/resumo-real-<AAAA-MM-DD>.json`.
  - **Sem IPs:** o contrato não tem campo de IP, e o teste verifica que nenhum IP do banco de teste aparece no arquivo gerado.
  - **Filtro de IPs da equipe:** a isca **não tem** um hoje (conferido em 06/11), então o comando também não aplica. Se um filtro for criado, ele entra nos dois lugares.
  - **Teste:** a partir de um SQLite de teste, o comando gera um resumo que valida no `core` e não contém nenhum IP.
- **Painel:** usa o `resumo-real-*.json` mais recente quando existir; senão, cai no `resumo-congelado.json`. O cartão mostra a origem: **"Ataques reais, congelados em <data>"** ou **"Dados de exemplo"**.
- **Rotas da demo com o resumo real:** conferido em 06/11, com a proporção real da isca na EC2 (198 Telnet e 2 MQTT): rotas e custos **idênticos** aos do resumo de exemplo (inseguro pela câmera, custo 1,422; seguro pelo roteador, custo 4,856). Um teste trava isso para o resumo real versionado. Se um resumo real futuro mudar as rotas, o Lucas é avisado **antes** de qualquer calibragem.
- **Senha da câmera (decidido em 06/11):** o perfil inseguro e as evidências passam a usar a credencial mais tentada do **resumo real** versionado, não a do resumo de exemplo. Assim a frase da demo ("configuramos a câmera com a senha que os atacantes mais tentaram") bate com o cartão. Entra na entrega 3, junto com o exportador, e o teste das fixtures passa a conferir a coerência com o resumo real.
- **Formigas de ataque:** saem num ritmo fixo e lento (1 a cada 2 s). O serviço de cada uma é sorteado na proporção de `por_servico` do resumo em uso, e a tela diz isso ("ritmo baseado nos ataques congelados em <data>"). Quando o `intel` existir, sai uma formiga para cada aumento de `acumulado_por_servico` (spec-mãe, seção 11), e só o adaptador muda.

### 3.8 Replay (plano B offline)

- **Gravação:** um novo comando, `honeyant-gravar-replay` (em `apps/`), grava `docs/demo/replay-inseguro.jsonl` e `docs/demo/replay-seguro.jsonl` com a semente 42. Ele usa o `GravadorDeReplay` (`pathfinder/adapters/replay.py`). Os dois arquivos são versionados.
- **Arquivos sempre atualizados:** um teste regenera os dois replays **em memória** e compara com os arquivos commitados, no mesmo estilo do teste do JSON Schema. Se as fixtures mudarem, o CI acusa. A mensagem de falha diz: "rode `uv run honeyant-gravar-replay` e faça commit de `docs/demo/replay-*.jsonl`".
- **Sem arquivo:** o botão "Replay" fica desabilitado, com o motivo no `title` e em texto, se `/api/v1/replay` disser que o arquivo não existe.

### 3.9 Proteção contra DNS rebinding

- **O ataque:** escutar só em 127.0.0.1 não basta. Um site malicioso aberto no mesmo navegador pode apontar um domínio para 127.0.0.1 e ler a API.
- **A defesa:** o `TrustedHostMiddleware` do Starlette (sem dependência nova).
  - No modo local, `criar_app(..., hosts_permitidos=("127.0.0.1", "localhost"))`.
  - No modo nuvem, os hosts vêm da configuração.
- **Teste:** uma requisição com `Host: evil.com` recebe 400. Os outros testes passam a usar `base_url="http://127.0.0.1"`.

## 4. A cena: rede de túneis em grade

A casa é vista **de cima**, como uma rede de túneis em grade ortogonal, parecida com um mapa de metrô ou uma placa de circuito: só segmentos horizontais e verticais, com cantos em ângulo reto. A rede substitui a cena 2.5D (câmaras ovais, túneis curvos e corte do solo), que sai inteira.

### 4.1 Grade e fundo

- **Grade:** `viewBox="0 0 1000 640"` com passo `GRADE = 10`. Todo ponto da cena (entradas, cantos dos túneis e túneis de fundo) cai num múltiplo de 10. As posições das entradas vêm do `PerfilDaCasa`, cujas coordenadas atuais já são múltiplos de 10, então o `core` não muda.
- **Fundo:** grafite liso, sem textura, céu, camadas de terra ou perspectiva. A inclinação ao mover o mouse sai junto com a cena 2.5D.

### 4.2 Entradas

- **Dispositivo:** cada nó é uma **entrada** na grade, um círculo de raio `RAIO_ENTRADA = 22` com borda e o ícone dentro. Os ícones vêm de `static/icones.svg` (`<symbol>` + `<use>`).
- **Nome:** fica ao lado da entrada, em texto (`textContent`). O lado (`acima`, `abaixo`, `esquerda` ou `direita`) vem do `layout.json`, para nenhum nome cair sobre um túnel. Um teste confere que a caixa de cada nome não cruza nenhum túnel.
- **Internet:** fica na borda da cena, como a entrada externa. É um meio-círculo encostado na borda, com o rótulo "Internet".
- **Fechadura:** é um quadrado de lado 48 com borda dupla e destaque permanente. A forma diferente da das outras entradas também carrega o sinal, não só a cor.

### 4.3 Túneis

- **Traçado:** cada aresta vira um caminho ortogonal entre as duas entradas. Os **cantos** de cada túnel ficam em `static/layout.json`, ajustados à mão. Não há algoritmo de roteamento.

  ```json
  {
    "grade": 10,
    "rotulos": {"camera": "esquerda", "...": "..."},
    "tuneis": {"camera->broker": [[220, 450]], "...": [[0, 0]]},
    "decoracao": [[[0, 120], [160, 120], [160, 300]], "..."]
  }
  ```

  Em `tuneis`, cada lista tem só os cantos internos. O caminho completo é `[origem, ...cantos, destino]`.
- **Testes sobre os dados** (os dois perfis):
  - **ortogonal:** cada segmento é horizontal ou vertical, e todo ponto está na grade;
  - **folga:** nenhum túnel passa a menos de `RAIO_ENTRADA + FOLGA` (`FOLGA = 12`) do centro de uma entrada que não é ponta dele;
  - **sem sobreposição:** dois túneis podem se **cruzar**, mas não correr um em cima do outro (segmentos colineares com trecho em comum);
  - **cobertura:** toda aresta dos perfis tem entrada em `tuneis`;
  - **o teste morde:** sem os cantos do layout (ligação direta), o teste de folga acusa pelo menos um túnel.
- **Estados:**

| Estado | Visual |
|---|---|
| Normal | Tom escuro e apagado. A espessura vai de 4 a 18 px, proporcional ao **uso pelas formigas** na iteração. O uso é guiado pelo feromônio; a medida exata está na nota abaixo. Transição suavizada entre snapshots |
| Rota prevista | Mais larga (22 px) e brilhante, em **âmbar**, com setas andando no sentido da invasão |
| Bloqueado | **Tracejado** e apagado, com cadeado no meio. O tracejado é exclusivo do bloqueado |
| Fundo (decoração) | Bem mais fraco que um túnel real, 3 px, sem formigas e sem estado |

> **Nota sobre a espessura.** Com os parâmetros calibrados do ACO (τ_max = 1, todas as formigas depositando), o feromônio satura no teto por volta da iteração 24: todas as arestas ficam iguais. Por isso a espessura segue o **tráfego de formigas da iteração**, isto é, quantas formigas de `caminhos` passaram por aquela aresta, relativo ao túnel mais usado. O tráfego é decidido pelo feromônio, então continua mostrando o que ele guia. Se o ACO for ajustado para não saturar, voltar a τ/τ_max é uma linha.

Um túnel é **bloqueado** quando a aresta está em `AnaliseDeRota.bloqueadas` do perfil exibido (lista explícita, seção 3.2). Uma aresta que falta num snapshot por outro motivo **não** vira cadeado: ela é desenhada com a espessura mínima.

### 4.4 Túneis de fundo (densidade)

- **O que são:** caminhos ortogonais **decorativos**, listados em `layout.json` (`decoracao`), para dar o efeito de rede densa. São escritos à mão, como os túneis reais.
- **Regras:**
  - são bem mais fracos que os reais e nunca recebem formigas, setas, cadeado ou estado;
  - respeitam a mesma folga das entradas;
  - podem cruzar túneis reais, mas não correr por cima deles.
- **Legenda:** traz um item próprio, "Túneis de fundo (só decoração)", com a amostra do traço fraco.

### 4.5 Formigas

- **Formigas do ACO:** quadrados **vermelho vivo** de 7 px, andando em linha reta pelos segmentos e virando nos cantos, pelos `caminhos` do snapshot. São no máximo **20** na tela.
- **Formigas de ataque real:** também vermelhas, mas com 9 px e contorno claro de 2 px. Entram pela entrada da internet (seção 3.7). O tamanho e o contorno diferenciam as duas, além da legenda.
- **Animação:**
  - um único laço de `requestAnimationFrame`;
  - a posição é calculada pela distância percorrida sobre a lista de segmentos, com o comprimento de cada túnel guardado em cache;
  - o máximo é um snapshot a cada 150 ms (o servidor já garante).
- **Sem animação:** com `prefers-reduced-motion`, nenhuma formiga anda, as setas ficam paradas e a cena mostra o estado final.

### 4.6 Desmoronamento

- **Sequência (~1,2 s):**
  1. o túnel câmera→broker pisca;
  2. o tracejado se abre das duas pontas para o meio, e alguns quadradinhos de "entulho" se espalham e somem;
  3. o cadeado aparece no meio.
- **Formigas:** as que estavam no túnel somem.
- **Sem animação:** com `prefers-reduced-motion`, a tela vai direto ao estado final.

### 4.7 Paleta e tipografia

- **Cores:**
  - fundo grafite escuro e liso;
  - túneis normais em cinza-azulado escuro e apagado; túneis de fundo ainda mais fracos;
  - **vermelho vivo** para as formigas (ACO e ataque real);
  - **âmbar** para a rota prevista e o alerta;
  - **verde-azulado** para "Protegida";
  - cinza claro para o tracejado e o cadeado do bloqueado.
- **Cor nunca é o único sinal:** a rota é mais larga e tem setas; o bloqueado tem tracejado e cadeado; a fechadura é quadrada e tem borda dupla; a formiga de ataque é maior e tem contorno.
- **Contraste:** AA em todo texto.
- **Fonte:** a do sistema, com `font-variant-numeric: tabular-nums` nos números. Não há arquivo de fonte.
- **Na implementação:** a direção final sai das skills de design (frontend-design / impeccable), dentro desses limites.

## 5. A página

### 5.1 Layout (1366×768)

```
cabeçalho: nome · selo do estado (Vulnerável / Protegida) · horário do resumo
controles: Prever invasão · velocidade (segmentado 0,25× a 4×) · Aplicar/Desfazer mitigação · Replay
principal: formigueiro (~70% da largura) | lateral (4 cartões)
rodapé da cena: legenda
```

### 5.2 Cartões do painel lateral

1. **Ataques reais (24 h):** total, barra por serviço, top 5 senhas, top 5 países.
2. **Rota prevista:** passos numerados; o **ponto fraco** (aresta de maior risco na rota) é marcado com ícone e texto.
3. **Antes e depois:** as duas rotas do Dijkstra, o custo de cada uma e o número grande `formatarComparativo(antes, depois)`, onde razão = `antes.plausibilidade / depois.plausibilidade`:
   - razão ≥ 2: "N× menos plausível", com N arredondado;
   - razão entre 1 e 2: "N% menos plausível";
   - `depois.rota` nula: "nenhuma rota até a fechadura".
4. **Dispositivos na rede:** tipo, categoria e nível de risco a partir de `riscos_por_no`. Faixas: < 0,3 baixo; < 0,6 médio; < 0,85 alto; senão crítico.

### 5.3 Controles e acessibilidade

- **Controles:** botões com hover, foco visível e estado desabilitado. Tudo acessível pelo teclado.
- **Leitor de tela:** uma região `aria-live="polite"` lê a rota em texto ("Rota prevista: Internet, Câmera, Broker, Fechadura. Ponto fraco: Câmera para Broker.").
- **Legenda:** descreve túnel, formiga do ACO, formiga de ataque, rota prevista e túnel bloqueado, sempre com forma **e** cor.

## 6. Segurança

- **DOM:** dados da isca e das fixtures entram **só** por `textContent` ou por atributos SVG definidos em código. Nunca `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` ou `new Function`.
- **CSP:** igual à atual (`default-src 'self'; script-src 'self'; ...`). O JS é carregado como `<script type="module" src>`, e não há script nem estilo inline.
- **Recursos:** sem CDN; ícones e CSS servidos pelo painel.
- **Rede:** continua só em 127.0.0.1 até o login entrar (seção 2), com o `TrustedHostMiddleware` contra DNS rebinding (seção 3.9).
- **Stream:** limites explícitos e um stream por cliente (seção 3.4); nenhum parâmetro do ACO vem do cliente.

## 7. Testes

| Tipo | Cobertura |
|---|---|
| JS (`node --test tests/js/`) | `estadoDoTunel`: espessura proporcional ao tráfego de formigas (com feromônio saturado, os túneis continuam diferentes); aresta em `bloqueadas` vira cadeado; aresta **ausente do feromônio sem estar bloqueada não vira cadeado**; rota destacada. `formatarComparativo`: razão grande ("N×"), razão pequena ("%"), sem rota. Grade: todo túnel e todo túnel de fundo é ortogonal e está na grade; nenhum passa a menos de `RAIO_ENTRADA + FOLGA` de entrada fora dele; nenhum corre por cima de outro; nenhum nome de entrada cruza um túnel; sem os cantos do layout, a folga acusa. `nivelDeRisco`: faixas |
| Python: painel | `/casa` nos dois perfis; `/resumo` com a origem (real ou exemplo); `/rotas` com ponto fraco, `riscos_por_no` e `bloqueadas`; stream com `perfil` e `modo=replay`; 404 sem replay; `/replay`; CSP em tudo; `Host: evil.com` → 400; cada limite da seção 3.4 → 422; "o mais novo vence"; proteção falsa → 401 em todas as rotas (seção 3.5) |
| Python: apps | `honeyant-gravar-replay` gera arquivos iguais aos snapshots do ACO com semente 42; **replays commitados iguais aos regenerados em memória**; `honeyant-exportar-resumo` gera resumo válido e sem IPs a partir de SQLite de teste; **último snapshot do ACO = Dijkstra** nos dois perfis (semente 42); rotas da demo iguais com o resumo real versionado; E2E da mitigação: inseguro pela câmera, seguro pelo roteador, **razão exibida = razão calculada pelo Dijkstra** |
| Segurança | rótulo `<script>` vira texto; varredura de **todos** os `.js` estáticos contra a lista proibida da seção 6; HTML sem script, estilo ou `on*` inline |
| CI | novo passo `actions/setup-node` (Node 20) + `node --test tests/js/` |
| Visual (Lucas) | dois perfis, mitigação, desfazer e replay no navegador; prints para o README e os slides |

## 8. Entregas (cada uma um PR)

0. **`feat/esqueleto-local`:** resolver o conflito do `pyproject.toml` com a `main` e abrir o PR.
1. **Página e formigueiro em grade com os dispositivos atuais:** seções 3.2 a 3.5, 3.9, 4, 5.1 e 5.3, a legenda e os testes JS da cena. O ponto de encaixe do login (3.5) entra aqui, para o Gustavo poder trabalhar em paralelo.
2. **Mitigação animada e comparativo:** seções 3.6, 4.6 e o cartão "Antes e depois", mais o replay (3.8).
3. **Painel lateral com os dados da isca:** cartões 1, 2 e 4, `honeyant-exportar-resumo` e os ataques reais congelados (3.7).
4. **Novos dispositivos IoT (assistente de voz, geladeira, smart TV):** seção 9.
5. **Dispositivos pessoais detectados (notebook, celular):** o mínimo da seção 9.

Corte: último merge de funcionalidade em **08/11 às 18h**. As entregas 4 e 5 são as primeiras a sair. O que entrar precisa estar íntegro.

**Caminho crítico:** as entregas 3, 4 e 5 só começam se a **prova da vulnerabilidade real** (twin + capturas `.pcap` antes e depois) estiver encaminhada. Se ela estiver atrasada, o Lucas é avisado, porque ela tem prioridade sobre o painel: é o que o edital exige.

## 9. Dispositivos novos (entregas 4 e 5)

- **`core/casa.py`:**
  - `TipoDeNo` ganha `assistente_voz`, `geladeira`, `tv`, `notebook` e `celular`;
  - `No` ganha `categoria: Literal["infra", "iot", "pessoal"]` e `status: Literal["ativo", "detectado"] = "ativo"`;
  - a categoria tem um valor padrão derivado do tipo, para os perfis atuais continuarem válidos;
  - o JSON Schema é regenerado (`uv run honeyant-contratos`).
- **Fixtures:**
  - **Nós e arestas novos:** entram nos dois perfis, com coordenadas.
  - **Calibragem:** exposição e `fraqueza_fixa`/evidências calibradas para virarem **caminhos alternativos**, não atalhos.
  - **Detectados:** os dispositivos pessoais vêm com `status: "detectado"`.
- **Trava da demo:** um teste do pathfinder exige a rota `internet → câmera → broker → fechadura` no perfil inseguro e a passagem pelo roteador no seguro, com os nós novos.
- **Painel:** os dispositivos detectados aparecem como entrada de contorno tracejado e com o selo "detectado". O tracejado na entrada não se confunde com o do túnel bloqueado, porque a legenda diferencia os dois e o selo leva texto. Cada dispositivo novo precisa de cantos no `layout.json` e de lado para o nome.
- **Nomes genéricos:** nada de marcas, no código e na tela.
- **Ética:** nada de varrer redes reais; os dispositivos pessoais são declarados no perfil (a rede simulada da casa).
- **Dívida técnica declarada:**
  - containers desses dispositivos no twin;
  - detecção passiva pelo `sensor` (DHCP/ARP/mDNS/`client_id`).

## 10. Fora do escopo e dívida técnica

- **Login:** é o PR do Gustavo (encaixe na seção 3.5).
- **TLS e o painel na EC2:** ficam fora.
- **Roteamento automático dos túneis na grade:** melhoria futura. Hoje os cantos e os túneis de fundo são manuais (`static/layout.json`); com muitos dispositivos novos, ajustá-los à mão fica caro.
- O `intel` real e os ataques ao vivo.
- O `honeyant mitigar` real.
- O twin e o sensor.
- Three.js, D3 ou qualquer outra biblioteca (só com ADR).

## 11. Riscos

| Risco | Mitigação |
|---|---|
| A cena fica pesada no notebook | No máximo 20 formigas, um laço de `requestAnimationFrame`, comprimentos em cache; sem filtros nem texturas; túneis de fundo desenhados uma vez |
| Um túnel atravessa uma entrada ou corre por cima de outro | Cantos manuais no `layout.json`; os testes da grade falham no CI e apontam o túnel a ajustar |
| A banca confunde a mitigação do painel com a real | Nome do botão "(perfil seguro)" e a nota na cena apontando para `docs/capturas/`; a prova real vem do twin |
| O resumo real muda a rota da demo | Teste-trava da rota com o resumo real versionado; aviso ao Lucas antes de calibrar |
| Os dispositivos novos mudam a rota da demo | Teste-trava da rota (seção 9); os nós novos entram como alternativas, com exposição baixa |
| Faltar tempo | Ordem de entregas da seção 8; as 4 e 5 saem primeiro |
| Conflitos com o trabalho dos colegas | O `core` muda num PR próprio, antes do painel; o painel só consome contratos |
