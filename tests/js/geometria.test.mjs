import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  caminhoDoTunel, ehOrtogonal, naGrade, comprimento, pontoNoCaminho, invadeEntrada,
  sobreposicao, caixaDoRotulo, cruzaCaixa, GRADE, RAIO_ENTRADA, FOLGA,
} from "../../src/honeyant/painel/static/js/geometria.js";

const raiz = new URL("../../", import.meta.url);
const ler = (caminho) => JSON.parse(readFileSync(new URL(caminho, raiz), "utf-8"));
const layout = ler("src/honeyant/painel/static/layout.json");
const perfis = ["inseguro", "seguro"].map((p) => ler(`docs/demo/perfil-${p}.json`));

// Todos os túneis de um perfil: reais (com as pontas) e de fundo.
function tuneis(perfil, lay) {
  const porId = Object.fromEntries(perfil.nos.map((n) => [n.id, n]));
  const reais = perfil.arestas.map((a) => ({
    nome: `${a.origem}->${a.destino}`,
    pontas: [porId[a.origem], porId[a.destino]],
    caminho: caminhoDoTunel(porId[a.origem], porId[a.destino], lay),
  }));
  const fundo = (lay.decoracao ?? []).map((caminho, i) => ({ nome: `fundo ${i}`, pontas: [], caminho }));
  return [...reais, ...fundo];
}

test("constantes da geometria", () => {
  assert.deepEqual([GRADE, RAIO_ENTRADA, FOLGA], [10, 22, 12]);
});

test("caminho usa os cantos do layout entre as pontas", () => {
  const a = { id: "a", x: 0, y: 0 };
  const b = { id: "b", x: 100, y: 50 };
  assert.deepEqual(caminhoDoTunel(a, b, { tuneis: { "a->b": [[100, 0]] } }), [[0, 0], [100, 0], [100, 50]]);
  assert.deepEqual(caminhoDoTunel(a, b, {}), [[0, 0], [100, 50]]);
});

test("ortogonal e grade", () => {
  assert.equal(ehOrtogonal([[0, 0], [100, 0], [100, 50]]), true);
  assert.equal(ehOrtogonal([[0, 0], [100, 50]]), false);
  assert.equal(naGrade([[0, 0], [100, 50]]), true);
  assert.equal(naGrade([[0, 0], [105, 50]]), false);
});

test("comprimento e ponto no caminho viram no canto", () => {
  const c = [[0, 0], [100, 0], [100, 50]];
  assert.equal(comprimento(c), 150);
  assert.deepEqual(pontoNoCaminho(c, 40), { x: 40, y: 0, dx: 1, dy: 0 });
  assert.deepEqual(pontoNoCaminho(c, 120), { x: 100, y: 20, dx: 0, dy: 1 });
  assert.deepEqual(pontoNoCaminho(c, 999), { x: 100, y: 50, dx: 0, dy: 1 });
});

test("invadeEntrada respeita raio e folga", () => {
  const reta = [[0, 100], [300, 100]];
  const limite = RAIO_ENTRADA + FOLGA;
  assert.equal(invadeEntrada(reta, { x: 150, y: 100 + limite - 1 }), true);
  assert.equal(invadeEntrada(reta, { x: 150, y: 100 + limite + 1 }), false);
});

test("sobreposicao mede trechos colineares e desconta as zonas das pontas comuns", () => {
  const a = [[0, 0], [200, 0]];
  assert.equal(sobreposicao(a, [[100, 0], [300, 0]]), 100);
  assert.equal(sobreposicao(a, [[0, 10], [200, 10]]), 0); // paralelos, não juntos
  assert.equal(sobreposicao(a, [[100, -50], [100, 50]]), 0); // cruzamento
  // Saindo da mesma entrada em (0, 0): os primeiros 34 px não contam.
  assert.equal(sobreposicao(a, [[0, 0], [30, 0]], [{ x: 0, y: 0 }]), 0);
});

test("caixa do rótulo fica do lado pedido", () => {
  const no = { x: 100, y: 100 };
  const direita = caixaDoRotulo(no, "direita", "abcd");
  assert.ok(direita.x0 > no.x + RAIO_ENTRADA);
  assert.equal(direita.ancora, "start");
  const acima = caixaDoRotulo(no, "acima", "abcd");
  assert.ok(acima.y1 < no.y - RAIO_ENTRADA);
  assert.equal(cruzaCaixa([[0, 100], [300, 100]], caixaDoRotulo(no, "esquerda", "abcd")), true);
  assert.equal(cruzaCaixa([[0, 300], [300, 300]], caixaDoRotulo(no, "esquerda", "abcd")), false);
});

test("o layout cobre todas as arestas e todos os nomes", () => {
  for (const p of perfis) {
    for (const a of p.arestas) assert.ok(layout.tuneis[`${a.origem}->${a.destino}`], `${a.origem}->${a.destino}`);
    for (const n of p.nos) assert.ok(layout.rotulos[n.id], n.id);
  }
});

test("túneis ortogonais e na grade", () => {
  for (const p of perfis) {
    for (const t of tuneis(p, layout)) {
      assert.ok(ehOrtogonal(t.caminho), `${p.perfil}: ${t.nome} não é ortogonal`);
      assert.ok(naGrade(t.caminho), `${p.perfil}: ${t.nome} fora da grade`);
    }
  }
});

test("nenhum túnel invade entrada fora dele", () => {
  for (const p of perfis) {
    for (const t of tuneis(p, layout)) {
      for (const n of p.nos) {
        if (t.pontas.includes(n)) continue;
        assert.equal(invadeEntrada(t.caminho, n), false, `${p.perfil}: ${t.nome} invade ${n.id}`);
      }
    }
  }
});

test("nenhum túnel corre por cima de outro", () => {
  for (const p of perfis) {
    const todos = tuneis(p, layout);
    for (let i = 0; i < todos.length; i += 1) {
      for (let j = i + 1; j < todos.length; j += 1) {
        const comuns = todos[i].pontas.filter((n) => todos[j].pontas.includes(n));
        const junto = sobreposicao(todos[i].caminho, todos[j].caminho, comuns);
        assert.equal(junto, 0, `${p.perfil}: ${todos[i].nome} e ${todos[j].nome} correm juntos ${junto} px`);
      }
    }
  }
});

test("nenhum nome cruza túnel nem outro nome", () => {
  for (const p of perfis) {
    const caixas = p.nos.map((n) => [n.id, caixaDoRotulo(n, layout.rotulos[n.id], n.rotulo)]);
    for (const [id, caixa] of caixas) {
      assert.ok(caixa.x0 >= 0 && caixa.x1 <= 1000 && caixa.y0 >= 0 && caixa.y1 <= 640, `${id} fora da cena`);
      for (const t of tuneis(p, layout)) {
        assert.equal(cruzaCaixa(t.caminho, caixa), false, `${p.perfil}: nome de ${id} cruza ${t.nome}`);
      }
      for (const [outro, c2] of caixas) {
        if (outro === id) continue;
        const separadas = caixa.x1 < c2.x0 || c2.x1 < caixa.x0 || caixa.y1 < c2.y0 || c2.y1 < caixa.y0;
        assert.ok(separadas, `nomes de ${id} e ${outro} se sobrepõem`);
      }
    }
  }
});

test("sem os cantos do layout o teste de folga acusa", () => {
  const semCantos = { ...layout, tuneis: {}, decoracao: [] };
  const acusados = tuneis(perfis[0], semCantos).filter((t) =>
    perfis[0].nos.some((n) => !t.pontas.includes(n) && invadeEntrada(t.caminho, n)));
  assert.ok(acusados.some((t) => t.nome === "roteador->broker"));
});
