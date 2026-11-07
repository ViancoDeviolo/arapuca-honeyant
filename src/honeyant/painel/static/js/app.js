// Ligação da página: busca os dados, controla o stream e atualiza a cena e os textos.
// Dado da casa ou da isca só entra no DOM por textContent.

import { aceitarSnapshot } from "./estado.js";
import { criarCena } from "./cena.js";
import { formatarComparativo } from "./comparativo.js";

const $ = (id) => document.getElementById(id);
const SESSAO_EXPIRADA = "Sessão expirada. Entre de novo.";
const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

class SessaoExpirada extends Error {}

async function buscar(url) {
  const r = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (r.status === 401 || r.status === 403) throw new SessaoExpirada();
  if (!r.ok) throw new Error(`${url} respondeu ${r.status}`);
  return r.json();
}

function avisar(texto) {
  $("status").textContent = texto;
}

function velocidade() {
  const marcado = document.querySelector('input[name="velocidade"]:checked');
  return marcado ? marcado.value : "1";
}

function dataCurta(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(d);
}

function mostrarOrigem(resumo) {
  $("atualizado").textContent =
    resumo.origem === "real"
      ? `Ataques reais, congelados em ${dataCurta(resumo.resumo.gerado_em)}`
      : "Dados de exemplo";
}

function pontoFraco(analise) {
  let melhor = null;
  for (const [chave, risco] of Object.entries(analise.riscos)) {
    if (melhor === null || risco > melhor[1]) melhor = [chave, risco];
  }
  return melhor ? melhor[0].split("->") : null;
}

function mostrarRota(analise, rotulos) {
  const lista = $("passos");
  lista.replaceChildren();
  const fraco = $("ponto-fraco");
  if (!analise.rota) {
    fraco.textContent = "Nenhuma rota até a fechadura.";
    $("anuncio").textContent = "Nenhuma rota até a fechadura.";
    return;
  }
  const [deFraco, paraFraco] = pontoFraco(analise) ?? [];
  analise.rota.nos.forEach((id, i, nos) => {
    const li = document.createElement("li");
    li.textContent = rotulos[id] ?? id;
    const noFraco = (id === deFraco && nos[i + 1] === paraFraco) || (id === paraFraco && nos[i - 1] === deFraco);
    if (noFraco) li.classList.add("passo-fraco");
    lista.appendChild(li);
  });
  const nomes = analise.rota.nos.map((id) => rotulos[id] ?? id).join(", ");
  const textoFraco = deFraco ? `Ponto fraco: ${rotulos[deFraco]} para ${rotulos[paraFraco]}.` : "";
  fraco.textContent = textoFraco;
  $("anuncio").textContent = `Rota prevista: ${nomes}. ${textoFraco}`.trim();
}

const CUSTO = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const TUNEL_MITIGADO = "camera->broker";
const MOTIVO_SEM_REPLAY = "Sem arquivo de replay para este perfil. Rode uv run honeyant-gravar-replay.";

function estacao(texto, classe = "") {
  const li = document.createElement("li");
  if (classe) li.className = classe;
  for (const nome of ["trilho", "estacao"]) {
    const s = document.createElement("span");
    s.className = nome;
    s.setAttribute("aria-hidden", "true");
    li.appendChild(s);
  }
  li.appendChild(document.createTextNode(texto));
  return li;
}

function preencherLinha(lista, rota, rotulos) {
  lista.replaceChildren();
  if (!rota) {
    lista.appendChild(estacao("nenhuma rota até a fechadura", "sem-rota"));
    return;
  }
  for (const id of rota.nos) lista.appendChild(estacao(rotulos[id] ?? id));
}

function mostrarComparativo(rotas, rotulos) {
  const antes = rotas.inseguro.rota;
  const depois = rotas.seguro.rota;
  $("comparativo-numero").textContent = antes ? formatarComparativo(antes, depois).titulo : "";
  preencherLinha($("linha-antes"), antes, rotulos);
  preencherLinha($("linha-depois"), depois, rotulos);
  $("custo-antes").textContent = antes ? `custo ${CUSTO.format(antes.custo)}` : "";
  $("custo-depois").textContent = depois ? `custo ${CUSTO.format(depois.custo)}` : "";
}

async function iniciar() {
  const [casaInsegura, rotas, layout, resumo, replays, sessao] = await Promise.all([
    buscar("/api/v1/casa?perfil=inseguro"),
    buscar("/api/v1/rotas"),
    buscar("/static/layout.json"),
    buscar("/api/v1/resumo"),
    buscar("/api/v1/replay"),
    buscar("/api/v1/sessao"),
  ]);
  // Com login ligado, o botão Sair (formulário POST /logout, sem JS) aparece no topo.
  $("form-sair").hidden = !sessao.login;
  const svg = $("formigueiro");
  let perfil = "inseguro";
  let casa = casaInsegura;
  let rotulos = Object.fromEntries(casa.nos.map((n) => [n.id, n.rotulo]));
  let analise = rotas[perfil];
  let cena = criarCena(svg, casa, layout, { reduzido });
  mostrarOrigem(resumo);
  mostrarComparativo(rotas, rotulos);

  let fonte = null;
  let atual = null;
  let ultimo = null;
  let ocupado = false;

  function fecharStream() {
    if (fonte) fonte.close();
    fonte = null;
  }

  function estadoInicial() {
    cena.limpar(analise);
    $("passos").replaceChildren();
    $("ponto-fraco").textContent = "Clique em Prever invasão para ver a rota.";
  }

  function atualizarControles() {
    const protegida = perfil === "seguro";
    const temReplay = Boolean(replays[perfil]);
    $("prever").disabled = ocupado;
    $("mitigar").disabled = ocupado;
    $("mitigar").textContent = protegida ? "Desfazer mitigação" : "Aplicar mitigação (perfil seguro)";
    $("mitigar").classList.toggle("botao-desfazer", protegida);
    $("replay").disabled = ocupado || !temReplay;
    $("replay").title = temReplay ? "Reproduz a exploração gravada, sem rodar o ACO" : MOTIVO_SEM_REPLAY;
    $("motivo-replay").textContent = temReplay ? "" : MOTIVO_SEM_REPLAY;
    $("motivo-replay").hidden = temReplay;
    const selo = $("selo");
    selo.textContent = protegida ? "Protegida" : "Vulnerável";
    selo.className = `selo ${protegida ? "selo-protegida" : "selo-vulneravel"}`;
    $("nota-mitigacao").hidden = !protegida;
    $("trajeto-antes").setAttribute("aria-current", String(!protegida));
    $("trajeto-depois").setAttribute("aria-current", String(protegida));
    $("na-tela-antes").textContent = protegida ? "" : " (na tela)";
    $("na-tela-depois").textContent = protegida ? " (na tela)" : "";
  }

  function rodar(modo) {
    fecharStream();
    atual = null;
    ultimo = null;
    cena.limpar(analise);
    $("passos").replaceChildren();
    $("ponto-fraco").textContent = "";
    avisar(modo === "replay" ? "Reproduzindo a exploração gravada…" : "As formigas estão explorando a casa…");
    const params = new URLSearchParams({ perfil, modo, semente: "42", velocidade: velocidade() });
    const es = new EventSource(`/api/v1/formigueiro/stream?${params}`);
    fonte = es;
    es.addEventListener("snapshot", (ev) => {
      if (es !== fonte) return;
      const s = JSON.parse(ev.data);
      if (!aceitarSnapshot(atual, s)) return;
      atual = atual ?? s;
      ultimo = s;
      // Durante a exploração, só os túneis; a rota oficial (Dijkstra) aparece no fim.
      cena.aplicar(s, { rota: null, bloqueadas: analise.bloqueadas });
      avisar(`Iteração ${s.iteracao + 1}: as formigas reforçam os túneis mais fracos.`);
    });
    es.addEventListener("fim", () => {
      if (es !== fonte) return;
      fecharStream();
      if (ultimo) cena.aplicar(ultimo, analise);
      mostrarRota(analise, rotulos);
      avisar(
        analise.rota
          ? "Exploração concluída. A rota prevista está destacada em âmbar."
          : "Exploração concluída. Nenhuma rota chega à fechadura.",
      );
    });
    es.addEventListener("error", async () => {
      if (es !== fonte) return;
      fecharStream();
      try {
        await buscar(`/api/v1/casa?perfil=${perfil}`);
        avisar(
          modo === "replay"
            ? "O replay não pôde ser reproduzido. Clique em Prever invasão para rodar o ACO."
            : "A conexão caiu. Clique em Prever invasão para tentar de novo.",
        );
      } catch (erro) {
        avisar(erro instanceof SessaoExpirada ? SESSAO_EXPIRADA : "O painel não respondeu. Confira se ele está rodando.");
      }
    });
  }

  async function trocarPerfil(novo) {
    perfil = novo;
    casa = await buscar(`/api/v1/casa?perfil=${perfil}`);
    rotulos = Object.fromEntries(casa.nos.map((n) => [n.id, n.rotulo]));
    analise = rotas[perfil];
    cena = criarCena(svg, casa, layout, { reduzido });
  }

  $("prever").addEventListener("click", () => rodar("prever"));
  $("replay").addEventListener("click", () => rodar("replay"));
  $("mitigar").addEventListener("click", async () => {
    if (ocupado) return;
    ocupado = true;
    atualizarControles();
    fecharStream();
    try {
      if (perfil === "inseguro") {
        avisar("Aplicando a mitigação: o túnel Câmera → Broker desmorona.");
        await cena.desmoronar(TUNEL_MITIGADO);
        await trocarPerfil("seguro");
        ocupado = false;
        atualizarControles();
        rodar("prever");
        $("anuncio").textContent = "Mitigação aplicada. Casa protegida; as formigas procuram outra rota.";
      } else {
        await trocarPerfil("inseguro");
        ocupado = false;
        atualizarControles();
        estadoInicial();
        avisar("Mitigação desfeita. Clique em Prever invasão.");
        $("anuncio").textContent = "Mitigação desfeita. Casa vulnerável de novo.";
      }
    } catch (erro) {
      ocupado = false;
      atualizarControles();
      avisar(erro instanceof SessaoExpirada ? SESSAO_EXPIRADA : "Não foi possível trocar o perfil. Tente de novo.");
    }
  });

  estadoInicial();
  atualizarControles();
  avisar("Pronto. Clique em Prever invasão.");

  if (!reduzido) {
    const quadro = (agora) => {
      cena.animar(agora);
      requestAnimationFrame(quadro);
    };
    requestAnimationFrame(quadro);
  }
}

iniciar().catch((erro) => {
  avisar(erro instanceof SessaoExpirada ? SESSAO_EXPIRADA : "Não foi possível carregar a casa. Recarregue a página.");
});
