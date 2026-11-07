import { test } from "node:test";
import assert from "node:assert/strict";
import { formatarComparativo } from "../../src/honeyant/painel/static/js/comparativo.js";

const rota = (custo) => ({ nos: [], custo, plausibilidade: Math.exp(-custo), algoritmo: "dijkstra" });

test("razão grande vira 'N× menos plausível'", () => {
  const r = formatarComparativo(rota(1.422), rota(4.856));
  assert.ok(Math.abs(r.razao - Math.exp(4.856 - 1.422)) < 1e-9);
  assert.equal(r.titulo, "31× menos plausível");
});

test("razão entre 1 e 2 vira porcentagem", () => {
  const antes = { plausibilidade: 0.6 };
  const depois = { plausibilidade: 0.4 };
  const r = formatarComparativo(antes, depois);
  assert.ok(Math.abs(r.razao - 1.5) < 1e-12);
  assert.equal(r.titulo, "33% menos plausível");
});

test("sem rota depois da mitigação", () => {
  assert.deepEqual(formatarComparativo(rota(1.422), null), {
    titulo: "nenhuma rota até a fechadura",
    razao: null,
  });
});
