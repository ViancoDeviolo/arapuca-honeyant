# Painel e Formigueiro 2.5D: design (spec)

- **Data:** 2026-11-06
- **Status:** aprovado em conversa (abordagem A + seções 1 a 3); revisado com `AJUSTES-SPEC-PAINEL.md`; aguardando aprovação
- **Origem:** `docs/superpowers/BRIEFING-PAINEL-FORMIGUEIRO.md` e `docs/superpowers/specs/AJUSTES-SPEC-PAINEL.md`
- **Spec-mãe:** `docs/superpowers/specs/2026-11-05-arapuca-honeyant-design.md` (seções 3, 6, 11, 12 e 13 continuam valendo; onde este documento for mais específico, ele prevalece para o painel)
- **Base de código:** a branch `feat/esqueleto-local` (painel mínimo: FastAPI + SSE + SVG simples). Ela entra na `main` antes de qualquer entrega daqui.

---

## 1. Objetivo e critério de sucesso

Em poucos segundos, a banca precisa **ver a história da demonstração**:

> Hackers reais atacam a isca → formigas cavam túneis pela casa → o túnel principal chega à fechadura → aplicamos a mitigação → o túnel desmorona e as formigas são forçadas a um caminho bem pior.

**Pronto quando:**
1. a página abre em 1366×768 e no projetor com o formigueiro 2.5D;
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

- **Fábrica:** `criar_app(..., protecao: Sequence[Depends] = ())` recebe todas as dependências por parâmetro.
- **Routers:** todas as rotas ficam em dois `APIRouter`, o `api` (`/api/v1/*`) e o `pagina` (`/` e `/static/*`). Os dois são registrados com `dependencies=list(protecao)`, então o login protege tudo de uma vez.
- **Rotas do próprio login:** o PR do Gustavo inclui o router dele pela mesma fábrica, sem a proteção. Por exemplo, um parâmetro `routers_extras: Sequence[APIRouter] = ()` registrado antes dos protegidos.
- **Sem dependência implícita:** nenhum endpoint daqui assume que não há login. O JS trata 401 e 403 com "Sessão expirada. Entre de novo.", sem quebrar a cena. O stream usa o mesmo cookie (o `EventSource` envia cookies da mesma origem).
- **Teste do encaixe:** uma dependência de proteção falsa que sempre recusa (401) faz **todas** as rotas `/api/v1/*` e a página responderem 401.

### 3.6 Fluxo da mitigação (só no front, visual)

1. **Estado inicial:** `perfil = inseguro` e selo "Vulnerável".
2. **"Aplicar mitigação (perfil seguro)":** animação de desmoronamento do túnel câmera→broker (seção 4.5); `perfil = seguro`; um novo stream; selo "Protegida"; a nota "Simulação do perfil mitigado. A mitigação real e as capturas estão em `docs/capturas/`."; o botão vira "Desfazer mitigação".
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

## 4. A cena 2.5D

### 4.1 Corte do solo

- **Céu e solo:** no topo, uma faixa de céu e a linha do solo; a internet é a entrada na superfície.
- **Terra:** abaixo, **4 camadas** em tons que escurecem com a profundidade, com textura de ruído por filtro SVG (`feTurbulence`, sem imagem).
- **Inclinação ao mover o mouse:** no máximo 3°, via CSS `perspective` no contêiner. Ela é desligada com `prefers-reduced-motion`.

### 4.2 Câmaras

- **Formato:** elipse (largura > altura), com sombra interna e borda iluminada no alto.
- **Conteúdo:** ícone e nome **dentro** da câmara. Os ícones vêm de `static/icones.svg` (`<symbol>` + `<use>`), servido pelo próprio painel.
- **Túneis:** terminam na borda da elipse, então nenhum rótulo fica sobre um túnel.
- **Fechadura:** é a câmara mais funda, com borda dupla e destaque permanente.

### 4.3 Túneis

- **Traçado:** cada túnel é uma Bézier cúbica cujos **dois pontos de controle estão guardados num arquivo do painel**, `static/layout.json` (`{"<origem>-><destino>": [[cx1, cy1], [cx2, cy2]]}`). Eles são ajustados à mão uma vez, porque o layout é fixo. O contrato `PerfilDaCasa` não muda: o layout é assunto do painel, não do `core`.
  - **Sem entrada no layout:** o túnel usa uma curva padrão suave entre as duas câmaras, e o teste de folga acusa se ela atravessar alguma câmara.
  - **Teste de folga, agora sobre os dados:** nenhum túnel dos dois perfis passa a menos de `FOLGA` de uma câmara que não é ponta dele.
  - **Desvio automático** (`rotearTunel`): fica como melhoria futura (seção 10).
- **Camadas:** um corpo escuro com sombra e um miolo claro cujo brilho é proporcional ao feromônio.

| Estado | Visual |
|---|---|
| Normal | Largura de 4 a 22 px, proporcional a τ/τ_max do snapshot; ao evaporar, o túnel afina e escurece; transição suavizada entre snapshots |
| Rota prevista | Contínua, cor de alerta (âmbar), com brilho e chevrons andando no sentido da invasão |
| Bloqueado | **Tracejado**, apagado, com cadeado no meio. O tracejado é **exclusivo** do bloqueado |

Um túnel é **bloqueado** quando a aresta está em `AnaliseDeRota.bloqueadas` do perfil exibido (lista explícita, seção 3.2). Uma aresta que falta no `feromonio` de um snapshot por outro motivo **não** vira cadeado: ela é desenhada com a largura mínima.

### 4.4 Formigas

- **Formigas do ACO:** até **20** na tela, com corpo de três segmentos, percorrendo os `caminhos` do snapshot.
- **Formigas de ataque:** cor violeta e contorno marcado; entram pela superfície (seção 3.5).
- **Animação:** um único laço de `requestAnimationFrame`, com o comprimento de cada curva guardado em cache. O máximo é um snapshot a cada 150 ms (o servidor já garante).

### 4.5 Desmoronamento

- **Sequência (~1,2 s):** rachaduras, partículas de terra caindo, depois o estado "bloqueado".
- **Formigas:** as que estavam no túnel somem.
- **Sem animação:** com `prefers-reduced-motion`, o desmoronamento não anima, e a tela vai direto ao estado final.

### 4.6 Paleta e tipografia

- **Cores:**
  - fundo grafite escuro;
  - terra em marrons dessaturados;
  - **âmbar** para alerta e rota;
  - **violeta** para ataque real;
  - **verde-azulado** para "Protegida".
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
| JS (`node --test tests/js/`) | `estadoDoTunel`: largura proporcional a τ; aresta em `bloqueadas` vira cadeado; aresta **ausente do feromônio sem estar bloqueada não vira cadeado**; rota destacada. `formatarComparativo`: razão grande ("N×"), razão pequena ("%"), sem rota. Folga dos túneis: nenhum túnel dos dois perfis, com o `layout.json`, passa a menos de `FOLGA` de câmara fora dele. `nivelDeRisco`: faixas |
| Python: painel | `/casa` nos dois perfis; `/resumo` com a origem (real ou exemplo); `/rotas` com ponto fraco, `riscos_por_no` e `bloqueadas`; stream com `perfil` e `modo=replay`; 404 sem replay; `/replay`; CSP em tudo; `Host: evil.com` → 400; cada limite da seção 3.4 → 422; "o mais novo vence"; proteção falsa → 401 em todas as rotas (seção 3.5) |
| Python: apps | `honeyant-gravar-replay` gera arquivos iguais aos snapshots do ACO com semente 42; **replays commitados iguais aos regenerados em memória**; `honeyant-exportar-resumo` gera resumo válido e sem IPs a partir de SQLite de teste; **último snapshot do ACO = Dijkstra** nos dois perfis (semente 42); rotas da demo iguais com o resumo real versionado; E2E da mitigação: inseguro pela câmera, seguro pelo roteador, **razão exibida = razão calculada pelo Dijkstra** |
| Segurança | rótulo `<script>` vira texto; varredura de **todos** os `.js` estáticos contra a lista proibida da seção 6; HTML sem script, estilo ou `on*` inline |
| CI | novo passo `actions/setup-node` (Node 20) + `node --test tests/js/` |
| Visual (Lucas) | dois perfis, mitigação, desfazer e replay no navegador; prints para o README e os slides |

## 8. Entregas (cada uma um PR)

0. **`feat/esqueleto-local`:** resolver o conflito do `pyproject.toml` com a `main` e abrir o PR.
1. **Página e formigueiro 2.5D com os dispositivos atuais:** seções 3.2 a 3.5, 3.9, 4, 5.1 e 5.3, a legenda e os testes JS da cena. O ponto de encaixe do login (3.5) entra aqui, para o Gustavo poder trabalhar em paralelo.
2. **Mitigação animada e comparativo:** seções 3.6, 4.5 e o cartão "Antes e depois", mais o replay (3.8).
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
- **Painel:** os dispositivos detectados aparecem com câmara de contorno tracejado e o selo "detectado". O tracejado na câmara não se confunde com o do túnel bloqueado, porque a legenda diferencia os dois e o selo leva texto.
- **Nomes genéricos:** nada de marcas, no código e na tela.
- **Ética:** nada de varrer redes reais; os dispositivos pessoais são declarados no perfil (a rede simulada da casa).
- **Dívida técnica declarada:**
  - containers desses dispositivos no twin;
  - detecção passiva pelo `sensor` (DHCP/ARP/mDNS/`client_id`).

## 10. Fora do escopo e dívida técnica

- **Login:** é o PR do Gustavo (encaixe na seção 3.5).
- **TLS e o painel na EC2:** ficam fora.
- **Desvio automático dos túneis** (`rotearTunel`): melhoria futura. Hoje os pontos de controle são manuais (`static/layout.json`); com muitos dispositivos novos, ajustá-los à mão fica caro.
- O `intel` real e os ataques ao vivo.
- O `honeyant mitigar` real.
- O twin e o sensor.
- Three.js, D3 ou qualquer outra biblioteca (só com ADR).

## 11. Riscos

| Risco | Mitigação |
|---|---|
| A cena 2.5D fica pesada no notebook | No máximo 20 formigas, um laço de `requestAnimationFrame`, comprimentos em cache, filtro de textura aplicado uma vez no fundo |
| Um túnel atravessa uma câmara | Pontos de controle manuais no `layout.json`; o teste de folga falha no CI e aponta o túnel a ajustar |
| A banca confunde a mitigação do painel com a real | Nome do botão "(perfil seguro)" e a nota na cena apontando para `docs/capturas/`; a prova real vem do twin |
| O resumo real muda a rota da demo | Teste-trava da rota com o resumo real versionado; aviso ao Lucas antes de calibrar |
| Os dispositivos novos mudam a rota da demo | Teste-trava da rota (seção 9); os nós novos entram como alternativas, com exposição baixa |
| Faltar tempo | Ordem de entregas da seção 8; as 4 e 5 saem primeiro |
| Conflitos com o trabalho dos colegas | O `core` muda num PR próprio, antes do painel; o painel só consome contratos |
