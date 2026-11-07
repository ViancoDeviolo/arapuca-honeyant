// Rede de túneis em grade ortogonal, vista de cima (spec do painel, seção 4). Só desenha.
// Todo texto vindo da casa entra por textContent; atributos SVG são definidos por código.

import { aceitarSnapshot, estadoDoTunel } from "./estado.js";
import { caixaDoRotulo, caminhoDoTunel, comprimento, pontoNoCaminho, RAIO_ENTRADA } from "./geometria.js";

const NS = "http://www.w3.org/2000/svg";
const ICONES = "/static/icones.svg";
export const MAX_FORMIGAS = 20;
const LADO_FORMIGA = 7;
const VELOCIDADE_PX_S = 150;
const SETAS_POR_TUNEL = 3;
const BORDA_EXTERNA = 14; // linha da borda da cena, onde fica a entrada da internet
const LADO_FECHADURA = 48;

function el(nome, atributos = {}, pai = null) {
  const e = document.createElementNS(NS, nome);
  for (const [k, v] of Object.entries(atributos)) e.setAttribute(k, String(v));
  if (pai) pai.appendChild(e);
  return e;
}

const caminhoD = (pontos) => pontos.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
const angulo = ({ dx, dy }) => (Math.atan2(dy, dx) * 180) / Math.PI;

function desenharEntrada(g, n, casa) {
  if (n.id === casa.origem) {
    // Entrada externa: meio-círculo encostado na borda da cena.
    const r = RAIO_ENTRADA + 12;
    const yb = BORDA_EXTERNA - n.y; // em coordenadas locais (o grupo está em n.x, n.y)
    el("path", { d: `M${-r} ${yb} A${r} ${r} 0 0 0 ${r} ${yb} Z`, class: "entrada-forma" }, g);
    el("use", { href: `${ICONES}#${n.tipo}`, x: -12, y: -14, width: 24, height: 24, class: "entrada-icone" }, g);
    return;
  }
  if (n.id === casa.alvo) {
    const l = LADO_FECHADURA;
    el("rect", { x: -l / 2 - 6, y: -l / 2 - 6, width: l + 12, height: l + 12, class: "entrada-anel" }, g);
    el("rect", { x: -l / 2, y: -l / 2, width: l, height: l, class: "entrada-forma" }, g);
  } else {
    el("circle", { r: RAIO_ENTRADA, class: "entrada-forma" }, g);
  }
  el("use", { href: `${ICONES}#${n.tipo}`, x: -12, y: -12, width: 24, height: 24, class: "entrada-icone" }, g);
}

export function criarCena(svg, casa, layout, { reduzido = false } = {}) {
  const grupo = (id) => svg.querySelector(`#${id}`);
  const gFundo = grupo("fundo");
  const gTuneis = grupo("tuneis");
  const gSetas = grupo("rota-sentido");
  const gFormigas = grupo("formigas");
  const gEntradas = grupo("entradas");
  for (const g of [gFundo, gTuneis, gSetas, gFormigas, gEntradas]) g.replaceChildren();

  el("line", { x1: -700, y1: BORDA_EXTERNA, x2: 1700, y2: BORDA_EXTERNA, class: "borda-externa" }, gFundo);
  for (const pontos of layout.decoracao ?? []) {
    el("path", { d: caminhoD(pontos), class: "tunel-fundo" }, gFundo);
  }

  const porId = Object.fromEntries(casa.nos.map((n) => [n.id, n]));
  const tuneis = new Map();
  for (const a of casa.arestas) {
    const chave = `${a.origem}->${a.destino}`;
    const pontos = caminhoDoTunel(porId[a.origem], porId[a.destino], layout);
    const g = el("g", { class: "tunel" }, gTuneis);
    const d = caminhoD(pontos);
    const base = el("path", { d, class: "tunel-base" }, g);
    const miolo = el("path", { d, class: "tunel-miolo" }, g);
    const total = comprimento(pontos);
    const meio = pontoNoCaminho(pontos, total / 2);
    el("use", {
      href: `${ICONES}#cadeado`, x: meio.x - 10, y: meio.y - 10, width: 20, height: 20, class: "cadeado",
    }, g);
    tuneis.set(chave, { g, base, miolo, pontos, comprimento: total });
  }

  for (const n of casa.nos) {
    const classes = ["entrada", `entrada-${n.tipo}`];
    if (n.id === casa.alvo) classes.push("entrada-alvo");
    if (n.id === casa.origem) classes.push("entrada-origem");
    const g = el("g", { class: classes.join(" "), transform: `translate(${n.x} ${n.y})` }, gEntradas);
    desenharEntrada(g, n, casa);
    const caixa = caixaDoRotulo(n, layout.rotulos?.[n.id] ?? "abaixo", n.rotulo);
    const nome = el("text", {
      x: caixa.x - n.x, y: caixa.y - n.y, class: "entrada-nome", "text-anchor": caixa.ancora,
    }, g);
    nome.textContent = n.rotulo;
  }

  let execucao = null;
  let formigas = [];
  let setas = [];
  let ultimoQuadro = null;

  function passosDe(nos) {
    const passos = [];
    for (let i = 0; i + 1 < nos.length; i += 1) {
      const t = tuneis.get(`${nos[i]}->${nos[i + 1]}`);
      if (!t || t.g.classList.contains("bloqueado")) return null;
      passos.push(t);
    }
    return passos.length ? passos : null;
  }

  function posicionar(elemento, tunel, distancia, centrar) {
    const p = pontoNoCaminho(tunel.pontos, distancia);
    const giro = centrar ? "" : ` rotate(${angulo(p)})`;
    elemento.setAttribute("transform", `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})${giro}`);
  }

  function distribuirFormigas(caminhos) {
    const validos = caminhos.map(passosDe).filter(Boolean).slice(0, MAX_FORMIGAS);
    while (formigas.length > validos.length) formigas.pop().g.remove();
    validos.forEach((passos, i) => {
      if (!formigas[i]) {
        const l = LADO_FORMIGA;
        const g = el("rect", { x: -l / 2, y: -l / 2, width: l, height: l, class: "formiga formiga-aco" }, gFormigas);
        // Espalha a largada para as formigas não andarem em fila.
        formigas[i] = { g, passos, passo: 0, distancia: (i * 37) % Math.max(1, passos[0].comprimento) };
      } else {
        formigas[i].proximos = passos; // troca o caminho no fim da volta atual
      }
    });
  }

  function desenharSetas(analise) {
    gSetas.replaceChildren();
    setas = [];
    const passos = analise?.rota ? passosDe(analise.rota.nos) : null;
    if (!passos) return;
    for (const tunel of passos) {
      for (let k = 0; k < SETAS_POR_TUNEL; k += 1) {
        const s = el("path", { d: "M-5 -5 L2 0 L-5 5", class: "seta" }, gSetas);
        const fase = (k + 0.5) / SETAS_POR_TUNEL;
        posicionar(s, tunel, fase * tunel.comprimento, false);
        setas.push({ s, tunel, fase });
      }
    }
  }

  function aplicar(snapshot, analise) {
    if (snapshot && !aceitarSnapshot(execucao, snapshot)) return false;
    if (snapshot) execucao = execucao ?? { execucao_id: snapshot.execucao_id };
    for (const [chave, tunel] of tuneis) {
      const e = estadoDoTunel(chave, snapshot, analise);
      tunel.miolo.style.strokeWidth = `${e.largura}px`;
      // Contorno escuro só um pouco mais largo que o túnel: separa dos túneis de fundo.
      tunel.base.style.strokeWidth = `${(e.rota ? 22 : e.largura) + 6}px`;
      tunel.miolo.style.opacity = String(0.45 + 0.55 * e.brilho);
      tunel.g.classList.toggle("rota", e.rota);
      tunel.g.classList.toggle("bloqueado", e.bloqueado);
    }
    desenharSetas(analise);
    if (!reduzido) distribuirFormigas(snapshot?.caminhos ?? []);
    return true;
  }

  function animar(agora) {
    if (reduzido) return;
    const dt = ultimoQuadro === null ? 0 : Math.min(0.1, (agora - ultimoQuadro) / 1000);
    ultimoQuadro = agora;
    const avanco = VELOCIDADE_PX_S * dt;
    for (const f of formigas) {
      f.distancia += avanco;
      while (f.distancia > f.passos[f.passo].comprimento) {
        f.distancia -= f.passos[f.passo].comprimento;
        f.passo += 1;
        if (f.passo >= f.passos.length) {
          f.passo = 0;
          if (f.proximos) {
            f.passos = f.proximos;
            f.proximos = null;
          }
        }
      }
      posicionar(f.g, f.passos[f.passo], f.distancia, true);
    }
    const ciclo = (agora / 1600) % 1;
    for (const s of setas) {
      const t = (s.fase + ciclo / SETAS_POR_TUNEL) % 1;
      posicionar(s.s, s.tunel, t * s.tunel.comprimento, false);
    }
  }

  function limpar(analise = null) {
    execucao = null;
    for (const f of formigas) f.g.remove();
    formigas = [];
    ultimoQuadro = null;
    aplicar(null, analise ? { rota: null, bloqueadas: analise.bloqueadas } : null);
  }

  return { aplicar, animar, limpar, tuneis };
}
