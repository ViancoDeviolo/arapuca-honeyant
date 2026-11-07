import { test } from "node:test";
import assert from "node:assert/strict";
import { estadoDoTunel, aceitarSnapshot } from "../../src/honeyant/painel/static/js/estado.js";

const snapshot = {
  execucao_id: "a",
  feromonio: { "internet->camera": 2, "camera->broker": 1, "broker->fechadura": 2 },
};
const analise = {
  rota: { nos: ["internet", "camera", "broker", "fechadura"] },
  bloqueadas: [],
};

test("largura proporcional ao feromônio", () => {
  assert.equal(estadoDoTunel("internet->camera", snapshot, analise).largura, 22);
  assert.equal(estadoDoTunel("camera->broker", snapshot, analise).largura, 13);
  assert.equal(estadoDoTunel("roteador->broker", snapshot, analise).largura, 4);
  assert.equal(estadoDoTunel("camera->broker", snapshot, analise).brilho, 0.5);
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
