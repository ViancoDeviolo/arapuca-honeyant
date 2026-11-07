// Rede de túneis em grade ortogonal, vista de cima (spec do painel, seção 4). Só desenha.
// Todo texto vindo da casa entra por textContent; atributos SVG são definidos por código.

import { aceitarSnapshot, estadoDoTunel } from "./estado.js";
import {
  caixaDoRotulo, caminhoDoTunel, comprimento, pontoNoCaminho, RAIO_ENTRADA, trecho,
} from "./geometria.js";

const NS = "http://www.w3.org/2000/svg";
const ICONES = "/static/icones.svg";
export const MAX_FORMIGAS = 20;
const LADO_FORMIGA = 7;
const VELOCIDADE_PX_S = 150;
const SETAS_POR_TUNEL = 3;
const BORDA_EXTERNA = 14; // linha da borda da cena, onde fica a entrada da internet
const LADO_FECHADURA = 48;
const DESMORONAMENTO_MS = 1200;
// Fases do desmoronamento, em fração da duração (spec 4.6): pisca, abre, cadeado.
const FIM_PISCA = 0.25;
const FIM_ABERTURA = 0.85;
const LADO_ENTULHO = 4;
const LADO_ATAQUE = 9;
const MAX_ATAQUES = 6;
// Alvo típico de cada serviço atacado na isca: Telnet procura câmeras (botnets do tipo
// Mirai); MQTT procura o broker, passando pelo roteador.
const CAMINHO_DO_ATAQUE = {
  telnet: ["internet", "camera"],
  mqtt: ["internet", "roteador", "broker"],
};

// Com "reduzir movimento", nenhuma formiga anda e o desmoronamento vai direto ao fim.
export function planoDeAnimacao(reduzido) {
  return reduzido
    ? { formigas: false, desmoronamentoMs: 0 }
    : { formigas: true, desmoronamentoMs: DESMORONAMENTO_MS };
}

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
  const plano = planoDeAnimacao(reduzido);
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
  let ataques = [];
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
    if (plano.formigas) distribuirFormigas(snapshot?.caminhos ?? []);
    return true;
  }

  function animar(agora) {
    if (!plano.formigas) return;
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
    ataques = ataques.filter((a) => {
      a.distancia += avanco * 0.8;
      while (a.distancia > a.passos[a.passo].comprimento) {
        a.distancia -= a.passos[a.passo].comprimento;
        a.passo += 1;
        if (a.passo >= a.passos.length) {
          a.g.remove(); // chegou ao alvo
          return false;
        }
      }
      posicionar(a.g, a.passos[a.passo], a.distancia, true);
      return true;
    });
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

  function soltarEntulho(ponto) {
    const l = LADO_ENTULHO;
    const r = el("rect", { x: -l / 2, y: -l / 2, width: l, height: l, class: "entulho" }, gFormigas);
    r.setAttribute("transform", `translate(${ponto.x.toFixed(1)} ${ponto.y.toFixed(1)})`);
    // Espalha para os lados do túnel (perpendicular ao trecho) e um pouco para a frente.
    const lado = Math.random() < 0.5 ? -1 : 1;
    const longe = 8 + Math.random() * 14;
    const dx = (ponto.dy !== 0 ? lado * longe : (Math.random() - 0.5) * 10);
    const dy = (ponto.dx !== 0 ? lado * longe : (Math.random() - 0.5) * 10);
    r.style.setProperty("--dx", `${dx.toFixed(1)}px`);
    r.style.setProperty("--dy", `${dy.toFixed(1)}px`);
    r.addEventListener("animationend", () => r.remove(), { once: true });
    setTimeout(() => r.remove(), 1000); // garantia, se a animação não rodar
  }

  // Desmorona um túnel (spec 4.6): pisca, o tracejado abre das pontas para o meio
  // soltando entulho, e o cadeado aparece. Resolve quando termina.
  function desmoronar(chave) {
    const tunel = tuneis.get(chave);
    if (!tunel) return Promise.resolve();
    for (const t of tuneis.values()) t.g.classList.remove("rota");
    gSetas.replaceChildren();
    setas = [];
    formigas = formigas.filter((f) => {
      const passa = f.passos.includes(tunel) || f.proximos?.includes(tunel);
      if (passa) f.g.remove();
      return !passa;
    });
    const terminar = () => {
      tunel.g.classList.remove("desmoronando");
      tunel.miolo.style.strokeDasharray = "";
      tunel.g.querySelectorAll(".ruina").forEach((r) => r.remove());
      tunel.g.classList.add("bloqueado", "recem-bloqueado");
    };
    if (plano.desmoronamentoMs === 0) {
      terminar();
      return Promise.resolve();
    }
    const total = tunel.comprimento;
    const ruinas = [0, 1].map(() => el("path", { class: "ruina" }, tunel.g));
    tunel.g.classList.add("desmoronando");
    return new Promise((resolver) => {
      const inicio = performance.now();
      let ultimoEntulho = 0;
      const passo = (agora) => {
        const t = Math.min(1, (agora - inicio) / plano.desmoronamentoMs);
        if (t >= FIM_PISCA) {
          tunel.g.classList.remove("desmoronando");
          const p = Math.min(1, (t - FIM_PISCA) / (FIM_ABERTURA - FIM_PISCA));
          const aberto = (p * total) / 2;
          // Miolo sólido só no meio que ainda não caiu; tracejado nas duas pontas.
          tunel.miolo.style.strokeDasharray = `0 ${aberto} ${Math.max(0, total - 2 * aberto)} ${total}`;
          ruinas[0].setAttribute("d", caminhoD(trecho(tunel.pontos, 0, aberto)));
          ruinas[1].setAttribute("d", caminhoD(trecho(tunel.pontos, total - aberto, total)));
          if (p < 1 && agora - ultimoEntulho > 70) {
            ultimoEntulho = agora;
            soltarEntulho(pontoNoCaminho(tunel.pontos, aberto));
            soltarEntulho(pontoNoCaminho(tunel.pontos, total - aberto));
          }
        }
        if (t >= FIM_ABERTURA) {
          terminar(); // o cadeado entra na última fase (CSS) antes de a promessa resolver
          setTimeout(resolver, plano.desmoronamentoMs * (1 - FIM_ABERTURA) + 60);
          return;
        }
        requestAnimationFrame(passo);
      };
      requestAnimationFrame(passo);
    });
  }

  // Formiga de ataque real (spec 4.5): quadrado vermelho de 9 px com contorno claro,
  // que entra pela internet. Desligada com "reduzir movimento".
  function soltarAtaque(servico) {
    if (!plano.formigas || ataques.length >= MAX_ATAQUES) return false;
    const passos = passosDe(CAMINHO_DO_ATAQUE[servico] ?? CAMINHO_DO_ATAQUE.telnet);
    if (!passos) return false;
    const l = LADO_ATAQUE;
    const g = el("rect", { x: -l / 2, y: -l / 2, width: l, height: l, class: "formiga formiga-ataque" }, gFormigas);
    posicionar(g, passos[0], 0, true);
    ataques.push({ g, passos, passo: 0, distancia: 0 });
    return true;
  }

  return { aplicar, animar, limpar, desmoronar, soltarAtaque, tuneis };
}
