// Ligação da página: busca os dados, controla o stream e atualiza a cena e os textos.
// Dado da casa ou da isca só entra no DOM por textContent.

import { aceitarSnapshot } from "./estado.js";
import { criarCena } from "./cena.js";
import { formatarComparativo } from "./comparativo.js";
import { maiores, nivelDeRisco, ROTULO_NIVEL, sortearServico } from "./risco.js";
import { acumuladoParaComparar, novosAtaques, textoDaOrigem } from "./aovivo.js";

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

function mostrarOrigem(resumo) {
  $("atualizado").textContent = textoDaOrigem(resumo);
}

const NS_SVG = "http://www.w3.org/2000/svg";
const NOME_SERVICO = { telnet: "Telnet", mqtt: "MQTT", http: "HTTP", upnp: "UPnP", lan: "LAN" };
const INTERVALO_ATAQUE_MS = 2000;
const INTERVALO_RESUMO_MS = 15000;
const NIVEIS = ["baixo", "medio", "alto", "critico"];
let nomesDePais = null;
try {
  nomesDePais = new Intl.DisplayNames(["pt-BR"], { type: "region" });
} catch {
  nomesDePais = null;
}

function nomeDoPais(codigo) {
  if (codigo === "ZZ") return "Desconhecido";
  try {
    return nomesDePais?.of(codigo) ?? codigo;
  } catch {
    return codigo;
  }
}

function itemComQuantidade(texto, quantidade) {
  const li = document.createElement("li");
  li.append(`${texto} `);
  const qtd = document.createElement("span");
  qtd.className = "qtd";
  qtd.textContent = `(${quantidade})`;
  li.appendChild(qtd);
  return li;
}

// Cartão "Ataques reais (24 h)". Senhas e países vêm da isca: só entram por textContent.
function mostrarAtaques(resumoComOrigem) {
  const r = resumoComOrigem.resumo;
  $("ataques-origem").textContent = textoDaOrigem(resumoComOrigem);
  const servicos = $("ataques-servicos");
  const senhas = $("ataques-senhas");
  const paises = $("ataques-paises");
  for (const lista of [servicos, senhas, paises]) lista.replaceChildren();
  if (r.total_eventos === 0) {
    $("ataques-total").textContent = "0";
    $("ataques-total-rotulo").textContent = "nenhum ataque nas últimas 24 h";
    return;
  }
  $("ataques-total").textContent = new Intl.NumberFormat("pt-BR").format(r.total_eventos);
  $("ataques-total-rotulo").textContent = "tentativas de invasão";
  const maior = Math.max(...Object.values(r.por_servico));
  for (const [servico, n] of maiores(r.por_servico, 5)) {
    const li = document.createElement("li");
    const nome = document.createElement("span");
    nome.textContent = NOME_SERVICO[servico] ?? servico;
    const trilho = document.createElement("span");
    trilho.className = "trilho-barra";
    const barra = document.createElement("span");
    barra.className = "barra";
    barra.style.width = `${(100 * n) / maior}%`;
    trilho.appendChild(barra);
    const numero = document.createElement("span");
    numero.className = "numero";
    numero.textContent = String(n);
    li.append(nome, trilho, numero);
    servicos.appendChild(li);
  }
  for (const c of r.top_credenciais.slice(0, 5)) {
    senhas.appendChild(itemComQuantidade(`${c.usuario ?? "–"} / ${c.senha ?? "–"}`, c.tentativas));
  }
  for (const [codigo, n] of maiores(r.por_pais, 5)) {
    paises.appendChild(itemComQuantidade(nomeDoPais(codigo), n));
  }
}

// Cartão "Dispositivos na rede": nível pelo maior risco das ligações de cada um.
function mostrarDispositivos(casa, analise) {
  const lista = $("dispositivos");
  lista.replaceChildren();
  for (const n of casa.nos) {
    if (n.id === casa.origem) continue;
    const nivel = nivelDeRisco(analise.riscos_por_no[n.id] ?? 0);
    const li = document.createElement("li");
    const icone = document.createElementNS(NS_SVG, "svg");
    icone.setAttribute("class", "icone");
    icone.setAttribute("viewBox", "0 0 24 24");
    icone.setAttribute("aria-hidden", "true");
    const uso = document.createElementNS(NS_SVG, "use");
    uso.setAttribute("href", `/static/icones.svg#${n.tipo}`);
    icone.appendChild(uso);
    const nome = document.createElement("span");
    nome.textContent = n.rotulo;
    const marca = document.createElement("span");
    marca.className = `nivel nivel-${nivel}`;
    const quadros = document.createElement("span");
    quadros.className = "quadros";
    quadros.setAttribute("aria-hidden", "true");
    NIVEIS.forEach((_, i) => {
      const q = document.createElement("span");
      if (i <= NIVEIS.indexOf(nivel)) q.className = "cheio";
      quadros.appendChild(q);
    });
    const texto = document.createElement("span");
    texto.className = "texto-nivel";
    texto.textContent = `risco ${ROTULO_NIVEL[nivel].toLowerCase()}`;
    marca.append(quadros, texto);
    li.append(icone, nome, marca);
    lista.appendChild(li);
  }
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
  mostrarAtaques(resumo);
  mostrarDispositivos(casa, analise);

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
    mostrarDispositivos(casa, analise);
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

  // Formigas de ataque. Ao vivo: uma por ataque novo na isca (diferença do acumulado
  // entre duas consultas). Fora do ao vivo: ritmo fixo de uma a cada 2 s, sorteada na
  // proporção do resumo. Nada com "reduzir movimento".
  let resumoAtual = resumo;
  let acumuladoAnterior = acumuladoParaComparar(resumo);

  function mostrarRitmo() {
    if (reduzido) return;
    const r = resumoAtual;
    if (r.origem === "ao_vivo") {
      $("ataques-ritmo").textContent = "Formigas de ataque na cena: uma por ataque novo recebido pela isca.";
    } else if (r.resumo.total_eventos > 0) {
      $("ataques-ritmo").textContent = "Formigas de ataque na cena: uma a cada 2 s, na proporção deste resumo.";
    } else {
      $("ataques-ritmo").textContent = "";
    }
  }
  mostrarRitmo();

  if (!reduzido) {
    setInterval(() => {
      if (resumoAtual.origem === "ao_vivo" || resumoAtual.resumo.total_eventos === 0) return;
      const servico = sortearServico(resumoAtual.resumo.por_servico);
      if (servico) cena.soltarAtaque(servico);
    }, INTERVALO_ATAQUE_MS);
  }

  // A cada 15 s, o resumo de novo: ao vivo (EC2), cache offline ou embutido.
  // A rota não muda: Prever, Mitigar e Replay usam o resumo embutido no servidor.
  setInterval(async () => {
    let novo;
    try {
      novo = await buscar("/api/v1/resumo");
    } catch {
      return; // o painel local não respondeu: tenta de novo na próxima
    }
    if (novo.origem === "ao_vivo" && !reduzido) {
      for (const servico of novosAtaques(acumuladoAnterior, novo.resumo.acumulado_por_servico)) {
        cena.soltarAtaque(servico);
      }
    }
    acumuladoAnterior = acumuladoParaComparar(novo);
    resumoAtual = novo;
    mostrarOrigem(novo);
    mostrarAtaques(novo);
    mostrarRitmo();
  }, INTERVALO_RESUMO_MS);

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
