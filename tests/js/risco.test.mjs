import { test } from "node:test";
import assert from "node:assert/strict";
import { maiores, nivelDeRisco, sortearServico } from "../../src/honeyant/painel/static/js/risco.js";

test("faixas de risco", () => {
  assert.equal(nivelDeRisco(0), "baixo");
  assert.equal(nivelDeRisco(0.29), "baixo");
  assert.equal(nivelDeRisco(0.3), "medio");
  assert.equal(nivelDeRisco(0.6), "alto");
  assert.equal(nivelDeRisco(0.85), "critico");
  assert.equal(nivelDeRisco(1), "critico");
});

test("sorteio proporcional aos ataques", () => {
  // mqtt vem antes de telnet na ordem alfabética: [0, 2) é mqtt, [2, 200) é telnet.
  assert.equal(sortearServico({ telnet: 198, mqtt: 2 }, () => 0.005), "mqtt");
  assert.equal(sortearServico({ telnet: 198, mqtt: 2 }, () => 0.5), "telnet");
  assert.equal(sortearServico({ telnet: 198, mqtt: 2 }, () => 0.995), "telnet");
});

test("sem ataques não sorteia nada", () => {
  assert.equal(sortearServico({}, () => 0.5), null);
  assert.equal(sortearServico({ telnet: 0 }, () => 0.5), null);
});

test("maiores ordena por contagem e desempata pela chave", () => {
  assert.deepEqual(maiores({ BR: 5, CN: 9, US: 5, RU: 1 }, 3), [["CN", 9], ["BR", 5], ["US", 5]]);
});
