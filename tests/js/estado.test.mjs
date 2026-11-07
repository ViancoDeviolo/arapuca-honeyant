import { test } from "node:test";
import assert from "node:assert/strict";
import { estadoDoTunel, aceitarSnapshot } from "../../src/honeyant/painel/static/js/estado.js";

// Duas formigas pela câmera e uma pelo roteador: internet->camera tem o dobro do tráfego.
const snapshot = {
  execucao_id: "a",
  feromonio: {
    "internet->camera": 1, "camera->broker": 1, "broker->fechadura": 1,
    "internet->roteador": 1, "roteador->broker": 1,
  },
  caminhos: [
    ["internet", "camera", "broker", "fechadura"],
    ["internet", "camera", "broker", "fechadura"],
    ["internet", "roteador", "broker", "fechadura"],
  ],
};
const analise = {
  rota: { nos: ["internet", "camera", "broker", "fechadura"] },
  bloqueadas: [],
};

test("largura proporcional ao tráfego de formigas na iteração", () => {
  // broker->fechadura: 3 formigas (máximo) → 18; internet->camera: 2 → 4 + 14·2/3; roteador: 1 → 4 + 14/3.
  const perto = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
  assert.equal(estadoDoTunel("broker->fechadura", snapshot, analise).largura, 18);
  perto(estadoDoTunel("internet->camera", snapshot, analise).largura, 4 + (14 * 2) / 3);
  perto(estadoDoTunel("roteador->broker", snapshot, analise).largura, 4 + 14 / 3);
  assert.equal(estadoDoTunel("lampada->broker", snapshot, analise).largura, 4);
  assert.equal(estadoDoTunel("roteador->broker", snapshot, analise).brilho, 1 / 3);
});

test("feromônio saturado não iguala os túneis", () => {
  // O ACO satura em τ_max (todas as arestas iguais); a largura segue o tráfego.
  const camera = estadoDoTunel("internet->camera", snapshot, analise).largura;
  const roteador = estadoDoTunel("internet->roteador", snapshot, analise).largura;
  assert.ok(camera > roteador);
});

test("aresta bloqueada vira cadeado", () => {
  const seguro = { rota: null, bloqueadas: ["camera->broker"] };
  assert.equal(estadoDoTunel("camera->broker", snapshot, seguro).bloqueado, true);
});

test("ausente do feromônio sem estar bloqueada não vira cadeado", () => {
  const e = estadoDoTunel("lampada->broker", snapshot, analise);
  assert.equal(e.bloqueado, false);
  assert.equal(e.largura, 4);
  assert.equal(e.brilho, 0);
});

test("rota destacada", () => {
  assert.equal(estadoDoTunel("camera->broker", snapshot, analise).rota, true);
  assert.equal(estadoDoTunel("roteador->broker", snapshot, analise).rota, false);
  // Sentido importa: broker->camera não é a rota.
  assert.equal(estadoDoTunel("broker->camera", snapshot, analise).rota, false);
});

test("sem snapshot nem rota, tudo no mínimo", () => {
  const e = estadoDoTunel("internet->camera", null, { rota: null, bloqueadas: [] });
  assert.deepEqual(e, { largura: 4, brilho: 0, rota: false, bloqueado: false });
});

test("snapshot de outra execução é recusado", () => {
  assert.equal(aceitarSnapshot(null, { execucao_id: "a" }), true);
  assert.equal(aceitarSnapshot({ execucao_id: "a" }, { execucao_id: "a" }), true);
  assert.equal(aceitarSnapshot({ execucao_id: "a" }, { execucao_id: "b" }), false);
});
