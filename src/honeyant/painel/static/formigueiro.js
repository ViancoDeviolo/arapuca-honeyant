// Formigueiro mínimo: desenha a casa (perfil) e engrossa os túneis conforme o feromônio
// de cada snapshot do ACO. Regra de segurança: texto vindo do servidor só por
// textContent; elementos só por createElementNS. Nada de HTML montado em string.
"use strict";

const SVG = "http://www.w3.org/2000/svg";
const ESPESSURA_MIN = 1;
const ESPESSURA_MAX = 12;
const RAIO = 28;

const tuneis = new Map(); // "a->b" -> <line>
let fonte = null;

function el(nome, atributos) {
  const e = document.createElementNS(SVG, nome);
  for (const [k, v] of Object.entries(atributos)) e.setAttribute(k, String(v));
  return e;
}

function status(texto) {
  document.getElementById("status").textContent = texto;
}

function desenharCasa(perfil) {
  document.getElementById("perfil").textContent = "Perfil: " + perfil.perfil;
  const posicao = new Map(perfil.nos.map((n) => [n.id, n]));
  const gTuneis = document.getElementById("tuneis");
  const gCamaras = document.getElementById("camaras");

  for (const a of perfil.arestas) {
    const o = posicao.get(a.origem);
    const d = posicao.get(a.destino);
    const linha = el("line", {
      x1: o.x, y1: o.y, x2: d.x, y2: d.y,
      class: "tunel", "stroke-width": ESPESSURA_MIN,
    });
    const titulo = el("title", {});
    titulo.textContent = a.origem + " → " + a.destino + " (" + a.servico + ")";
    linha.appendChild(titulo);
    gTuneis.appendChild(linha);
    tuneis.set(a.origem + "->" + a.destino, linha);
  }

  for (const n of perfil.nos) {
    const classe = n.id === perfil.alvo ? "camara alvo" : "camara";
    gCamaras.appendChild(el("circle", { cx: n.x, cy: n.y, r: RAIO, class: classe }));
    const rotulo = el("text", { x: n.x, y: n.y + RAIO + 22, class: "rotulo" });
    rotulo.textContent = n.rotulo;
    gCamaras.appendChild(rotulo);
  }
}

function aplicarSnapshot(s) {
  const valores = Object.values(s.feromonio);
  const maximo = valores.length ? Math.max(...valores) : 0;
  const naRota = new Set();
  if (s.melhor) {
    for (let i = 0; i + 1 < s.melhor.nos.length; i++) {
      naRota.add(s.melhor.nos[i] + "->" + s.melhor.nos[i + 1]);
    }
  }
  for (const [chave, linha] of tuneis) {
    const tau = s.feromonio[chave];
    const fracao = maximo > 0 && tau !== undefined ? tau / maximo : 0;
    const espessura = ESPESSURA_MIN + fracao * (ESPESSURA_MAX - ESPESSURA_MIN);
    linha.setAttribute("stroke-width", espessura.toFixed(1));
    linha.classList.toggle("rota", naRota.has(chave));
    // Aresta fora do grafo (bloqueada pela mitigação) não tem feromônio: some.
    linha.classList.toggle("bloqueado", tau === undefined);
    linha.setAttribute("visibility", tau === undefined ? "hidden" : "visible");
  }
  if (s.melhor) {
    status(
      "Iteração " + (s.iteracao + 1) + " — rota: " + s.melhor.nos.join(" → ") +
      " (plausibilidade " + s.melhor.plausibilidade.toFixed(3) + ")"
    );
  } else {
    status("Iteração " + (s.iteracao + 1) + " — sem rota até a fechadura");
  }
}

function prever() {
  if (fonte) fonte.close();
  const velocidade = document.getElementById("velocidade").value;
  const params = new URLSearchParams({ modo: "prever", semente: "42", velocidade });
  fonte = new EventSource("/api/v1/formigueiro/stream?" + params.toString());
  status("Calculando…");
  fonte.addEventListener("snapshot", (ev) => aplicarSnapshot(JSON.parse(ev.data)));
  fonte.addEventListener("fim", () => {
    fonte.close();
    fonte = null;
  });
  fonte.onerror = () => {
    status("Conexão com o painel perdida.");
    fonte.close();
    fonte = null;
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const resposta = await fetch("/api/v1/perfil");
    desenharCasa(await resposta.json());
  } catch (erro) {
    status("Não foi possível carregar o perfil da casa.");
    return;
  }
  document.getElementById("prever").addEventListener("click", prever);
});
