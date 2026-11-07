import { test } from "node:test";
import assert from "node:assert/strict";
import { novosAtaques, textoDaOrigem } from "../../src/honeyant/painel/static/js/aovivo.js";

const FUSO = "America/Sao_Paulo";
const resumo = (gerado_em = "2026-11-07T19:54:30Z") => ({ gerado_em });

test("uma formiga por incremento do acumulado, em ordem alfabética", () => {
  assert.deepEqual(novosAtaques({ telnet: 10, mqtt: 1 }, { telnet: 12, mqtt: 2 }), ["mqtt", "telnet", "telnet"]);
});

test("no máximo 6 formigas por consulta", () => {
  assert.equal(novosAtaques({ telnet: 0 }, { telnet: 50 }).length, 6);
});

test("sem consulta anterior, nenhuma formiga", () => {
  assert.deepEqual(novosAtaques(null, { telnet: 50 }), []);
});

test("contador que diminui (isca reiniciada) não solta formiga", () => {
  assert.deepEqual(novosAtaques({ telnet: 50 }, { telnet: 3 }), []);
});

test("serviço novo conta a partir de zero", () => {
  assert.deepEqual(novosAtaques({ telnet: 5 }, { telnet: 5, mqtt: 2 }), ["mqtt", "mqtt"]);
});

test("ao vivo mostra o horário local, não UTC", () => {
  const r = { origem: "ao_vivo", atualizado_em: "2026-11-08T15:04:00Z", resumo: resumo() };
  assert.equal(textoDaOrigem(r, FUSO), "Ao vivo · atualizado às 12:04");
});

test("offline mostra a data do último resumo ao vivo", () => {
  const r = { origem: "offline", atualizado_em: "2026-11-08T15:04:00Z", resumo: resumo() };
  assert.equal(textoDaOrigem(r, FUSO), "Resumo de 08/11/2026 12:04, offline");
});

test("real congelado e exemplo", () => {
  assert.equal(
    textoDaOrigem({ origem: "real", resumo: resumo() }, FUSO),
    "Ataques reais, congelados em 07/11/2026 16:54",
  );
  assert.equal(textoDaOrigem({ origem: "exemplo", resumo: resumo() }, FUSO), "Dados de exemplo");
});

test("aviso de chave inválida aparece junto da origem", () => {
  const r = { origem: "offline", atualizado_em: "2026-11-08T15:04:00Z", resumo: resumo(), aviso: "chave de acesso inválida" };
  assert.equal(textoDaOrigem(r, FUSO), "Resumo de 08/11/2026 12:04, offline · chave de acesso inválida");
});
