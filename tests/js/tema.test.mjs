import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { TEMAS, temaInicial } from "../../src/honeyant/painel/static/js/tema.js";

test("tema salvo e válido vence a preferência do sistema", () => {
  assert.equal(temaInicial("radar", true), "radar");
});

test("sem tema salvo, segue o sistema", () => {
  assert.equal(temaInicial(null, true), "papel");
  assert.equal(temaInicial(null, false), "noite");
});

test("valor salvo desconhecido ou herdado do protótipo é ignorado", () => {
  assert.equal(temaInicial("toString", false), "noite");
  assert.equal(temaInicial("<script>", true), "papel");
});

test("todo tema tem bloco no CSS e amostra no HTML", () => {
  const css = readFileSync(new URL("../../src/honeyant/painel/static/painel.css", import.meta.url), "utf8");
  const html = readFileSync(new URL("../../src/honeyant/painel/static/index.html", import.meta.url), "utf8");
  for (const tema of Object.keys(TEMAS)) {
    assert.ok(css.includes(`:root[data-tema="${tema}"]`), `CSS sem o tema ${tema}`);
    assert.ok(html.includes(`id="tema-${tema}" value="${tema}"`), `HTML sem a amostra ${tema}`);
  }
});
