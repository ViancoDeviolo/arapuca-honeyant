import { test } from "node:test";
import assert from "node:assert/strict";
import { planoDeAnimacao } from "../../src/honeyant/painel/static/js/cena.js";

test("com 'reduzir movimento', nada anda e o desmoronamento vai direto ao fim", () => {
  assert.deepEqual(planoDeAnimacao(true), { formigas: false, desmoronamentoMs: 0 });
});

test("sem preferência, formigas andam e o desmoronamento dura 1,2 s", () => {
  assert.deepEqual(planoDeAnimacao(false), { formigas: true, desmoronamentoMs: 1200 });
});
