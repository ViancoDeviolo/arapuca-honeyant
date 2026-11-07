import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  curvaDoTunel, pontoNaBezier, invadeCamara, CAMARA_RX, CAMARA_RY, FOLGA,
} from "../../src/honeyant/painel/static/js/geometria.js";

const raiz = new URL("../../", import.meta.url);
const ler = (caminho) => JSON.parse(readFileSync(new URL(caminho, raiz), "utf-8"));
const layout = ler("src/honeyant/painel/static/layout.json");
const perfis = ["inseguro", "seguro"].map((p) => ler(`docs/demo/perfil-${p}.json`));

function invasoes(perfil, lay) {
  const porId = Object.fromEntries(perfil.nos.map((n) => [n.id, n]));
  const achadas = [];
  for (const a of perfil.arestas) {
    const curva = curvaDoTunel(porId[a.origem], porId[a.destino], lay);
    for (const n of perfil.nos) {
      if (n.id !== a.origem && n.id !== a.destino && invadeCamara(curva, n)) {
        achadas.push(`${a.origem}->${a.destino} invade ${n.id}`);
      }
    }
  }
  return achadas;
}

test("constantes da geometria", () => {
  assert.deepEqual([CAMARA_RX, CAMARA_RY, FOLGA], [56, 34, 12]);
});

test("curva usa os pontos do layout ou terços do segmento", () => {
  const a = { id: "a", x: 0, y: 0 };
  const b = { id: "b", x: 300, y: 0 };
  assert.deepEqual(curvaDoTunel(a, b, {}), [[0, 0], [100, 0], [200, 0], [300, 0]]);
  assert.deepEqual(
    curvaDoTunel(a, b, { "a->b": [[10, 20], [30, 40]] }),
    [[0, 0], [10, 20], [30, 40], [300, 0]],
  );
});

test("ponto na Bézier nas pontas e no meio", () => {
  const c = [[0, 0], [0, 100], [100, 100], [100, 0]];
  assert.deepEqual(pontoNaBezier(c, 0), [0, 0]);
  assert.deepEqual(pontoNaBezier(c, 1), [100, 0]);
  assert.deepEqual(pontoNaBezier(c, 0.5), [50, 75]);
});

test("invadeCamara respeita a folga", () => {
  const reta = [[0, 100], [100, 100], [200, 100], [300, 100]];
  assert.equal(invadeCamara(reta, { x: 150, y: 100 + CAMARA_RY + FOLGA - 1 }), true);
  assert.equal(invadeCamara(reta, { x: 150, y: 100 + CAMARA_RY + FOLGA + 1 }), false);
});

test("o layout cobre todas as arestas dos dois perfis", () => {
  for (const p of perfis) {
    for (const a of p.arestas) assert.ok(layout[`${a.origem}->${a.destino}`], a.origem + a.destino);
  }
});

test("nenhum túnel invade câmara fora dele", () => {
  for (const p of perfis) assert.deepEqual(invasoes(p, layout), [], p.perfil);
});

test("sem layout o teste de folga pega a lâmpada", () => {
  assert.ok(invasoes(perfis[0], {}).includes("roteador->broker invade lampada"));
});
