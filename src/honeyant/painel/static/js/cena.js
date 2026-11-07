// Cena 2.5D do formigueiro (spec do painel, seção 4). Só desenha: não busca dados.
// Todo texto vindo da casa entra por textContent; atributos SVG são definidos por código.

import { aceitarSnapshot, estadoDoTunel } from "./estado.js";
import { curvaDoTunel } from "./geometria.js";

const NS = "http://www.w3.org/2000/svg";
const ICONES = "/static/icones.svg";
export const MAX_FORMIGAS = 20;
const VELOCIDADE_PX_S = 150;
const CHEVRONS_POR_TUNEL = 3;

function el(nome, atributos = {}, pai = null) {
  const e = document.createElementNS(NS, nome);
  for (const [k, v] of Object.entries(atributos)) e.setAttribute(k, String(v));
  if (pai) pai.appendChild(e);
  return e;
}

function caminhoD(curva) {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = curva;
  return `M${x0} ${y0} C${x1} ${y1} ${x2} ${y2} ${x3} ${y3}`;
}

function desenharFormiga(pai, classe) {
  const g = el("g", { class: `formiga ${classe}` }, pai);
  el("ellipse", { cx: -6, cy: 0, rx: 4, ry: 3 }, g);
  el("ellipse", { cx: 0, cy: 0, rx: 2.6, ry: 2.2 }, g);
  el("ellipse", { cx: 5, cy: 0, rx: 3, ry: 2.6 }, g);
  return g;
}

function posicao(tunel, distancia) {
  const d = Math.max(0, Math.min(distancia, tunel.comprimento));
  const p = tunel.miolo.getPointAtLength(d);
  const q = tunel.miolo.getPointAtLength(Math.min(d + 1, tunel.comprimento));
  const angulo = (Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI;
  return `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${angulo.toFixed(1)})`;
}

export function criarCena(svg, casa, layout, { reduzido = false } = {}) {
  const grupo = (id) => svg.querySelector(`#${id}`);
  const gTuneis = grupo("tuneis");
  const gSentido = grupo("rota-sentido");
  const gFormigas = grupo("formigas");
  const gCamaras = grupo("camaras");
  for (const g of [gTuneis, gSentido, gFormigas, gCamaras]) g.replaceChildren();

  const porId = Object.fromEntries(casa.nos.map((n) => [n.id, n]));
  const tuneis = new Map();

  for (const a of casa.arestas) {
    const chave = `${a.origem}->${a.destino}`;
    const curva = curvaDoTunel(porId[a.origem], porId[a.destino], layout);
    const g = el("g", { class: "tunel" }, gTuneis);
    const d = caminhoD(curva);
    const corpo = el("path", { d, class: "tunel-corpo" }, g);
    const miolo = el("path", { d, class: "tunel-miolo" }, g);
    const meio = { x: 0, y: 0 };
    const cadeado = el("use", { href: `${ICONES}#cadeado`, width: 20, height: 20, class: "cadeado" }, g);
    tuneis.set(chave, { g, corpo, miolo, cadeado, meio, comprimento: null });
  }

  for (const n of casa.nos) {
    const classes = ["camara", `camara-${n.tipo}`];
    if (n.id === casa.alvo) classes.push("camara-alvo");
    if (n.id === casa.origem) classes.push("camara-origem");
    const g = el("g", { class: classes.join(" "), transform: `translate(${n.x} ${n.y})` }, gCamaras);
    if (n.id === casa.alvo) el("ellipse", { rx: 64, ry: 42, class: "camara-anel" }, g);
    el("ellipse", { rx: 56, ry: 34, class: "camara-cavidade", fill: "url(#g-camara)", filter: "url(#f-escavado)" }, g);
    el("path", { d: "M-48 -14 A56 34 0 0 1 48 -14", class: "camara-borda" }, g);
    el("use", { href: `${ICONES}#${n.tipo}`, x: -12, y: -27, width: 24, height: 24, class: "camara-icone" }, g);
    const nome = el("text", { y: 16, class: "camara-nome", "text-anchor": "middle" }, g);
    nome.textContent = n.rotulo;
  }

  function medir(tunel) {
    if (tunel.comprimento === null) {
      tunel.comprimento = tunel.miolo.getTotalLength();
      const p = tunel.miolo.getPointAtLength(tunel.comprimento / 2);
      tunel.meio = { x: p.x, y: p.y };
      tunel.cadeado.setAttribute("x", (p.x - 10).toFixed(1));
      tunel.cadeado.setAttribute("y", (p.y - 10).toFixed(1));
    }
    return tunel;
  }

  let execucao = null;
  let formigas = [];
  let chevrons = [];
  let ultimoQuadro = null;

  function rotaValida(nos) {
    const passos = [];
    for (let i = 0; i + 1 < nos.length; i += 1) {
      const t = tuneis.get(`${nos[i]}->${nos[i + 1]}`);
      if (!t || t.g.classList.contains("bloqueado")) return null;
      passos.push(medir(t));
    }
    return passos.length ? passos : null;
  }

  function distribuirFormigas(caminhos) {
    const validos = caminhos.map(rotaValida).filter(Boolean).slice(0, MAX_FORMIGAS);
    while (formigas.length > validos.length) formigas.pop().g.remove();
    validos.forEach((passos, i) => {
      if (!formigas[i]) {
        formigas[i] = { g: desenharFormiga(gFormigas, "formiga-aco"), passos, passo: 0, distancia: 0 };
        // Espalha a largada para as formigas não andarem em fila.
        formigas[i].distancia = (i * 37) % Math.max(1, passos[0].comprimento);
      } else {
        formigas[i].proximos = passos; // troca o caminho ao fim do túnel atual
      }
    });
  }

  function desenharSentido(analise) {
    gSentido.replaceChildren();
    chevrons = [];
    const passos = analise?.rota ? rotaValida(analise.rota.nos) : null;
    if (!passos) return;
    for (const tunel of passos) {
      for (let k = 0; k < CHEVRONS_POR_TUNEL; k += 1) {
        const c = el("path", { d: "M-5 -5 L3 0 L-5 5", class: "chevron" }, gSentido);
        const fase = (k + 0.5) / CHEVRONS_POR_TUNEL;
        c.setAttribute("transform", posicao(tunel, fase * tunel.comprimento));
        chevrons.push({ c, tunel, fase });
      }
    }
  }

  function aplicar(snapshot, analise) {
    if (snapshot && !aceitarSnapshot(execucao, snapshot)) return false;
    if (snapshot) execucao = execucao ?? { execucao_id: snapshot.execucao_id };
    for (const [chave, tunel] of tuneis) {
      const e = estadoDoTunel(chave, snapshot, analise);
      tunel.corpo.style.strokeWidth = `${e.largura + 7}px`;
      tunel.miolo.style.strokeWidth = `${e.largura}px`;
      tunel.miolo.style.opacity = String(0.3 + 0.7 * e.brilho);
      tunel.g.classList.toggle("rota", e.rota);
      tunel.g.classList.toggle("bloqueado", e.bloqueado);
      if (e.bloqueado) medir(tunel);
    }
    desenharSentido(analise);
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
      f.g.setAttribute("transform", posicao(f.passos[f.passo], f.distancia));
    }
    const ciclo = (agora / 1600) % 1;
    for (const ch of chevrons) {
      const t = (ch.fase + ciclo / CHEVRONS_POR_TUNEL) % 1;
      ch.c.setAttribute("transform", posicao(ch.tunel, t * ch.tunel.comprimento));
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
