// Geometria da rede de túneis em grade ortogonal (spec do painel, seção 4).
// Funções puras: testadas com `node --test tests/js/`.

export const GRADE = 10;
export const RAIO_ENTRADA = 22;
export const FOLGA = 12;
const ZONA = RAIO_ENTRADA + FOLGA;
const ALTURA_ROTULO = 16;
const LARGURA_LETRA = 8; // estimativa conservadora para 14 px semibold
const AFASTAMENTO = RAIO_ENTRADA + 8;
const AFASTAMENTO_DIAGONAL = 18;

export function caminhoDoTunel(origem, destino, layout) {
  const cantos = layout?.tuneis?.[`${origem.id}->${destino.id}`] ?? [];
  return [[origem.x, origem.y], ...cantos, [destino.x, destino.y]];
}

function segmentos(caminho) {
  const lista = [];
  for (let i = 0; i + 1 < caminho.length; i += 1) lista.push([caminho[i], caminho[i + 1]]);
  return lista;
}

export function ehOrtogonal(caminho) {
  return segmentos(caminho).every(([[x0, y0], [x1, y1]]) => x0 === x1 || y0 === y1);
}

export function naGrade(caminho, grade = GRADE) {
  return caminho.every(([x, y]) => x % grade === 0 && y % grade === 0);
}

const tamanho = ([[x0, y0], [x1, y1]]) => Math.hypot(x1 - x0, y1 - y0);

export function comprimento(caminho) {
  return segmentos(caminho).reduce((soma, s) => soma + tamanho(s), 0);
}

export function pontoNoCaminho(caminho, distancia) {
  const lista = segmentos(caminho);
  let resto = Math.max(0, distancia);
  for (let i = 0; i < lista.length; i += 1) {
    const [[x0, y0], [x1, y1]] = lista[i];
    const t = tamanho(lista[i]);
    const dx = Math.sign(x1 - x0);
    const dy = Math.sign(y1 - y0);
    if (resto <= t || i === lista.length - 1) {
      const f = t === 0 ? 0 : Math.min(resto, t) / t;
      return { x: x0 + (x1 - x0) * f, y: y0 + (y1 - y0) * f, dx, dy };
    }
    resto -= t;
  }
  const [x, y] = caminho[0];
  return { x, y, dx: 0, dy: 0 };
}

// Pedaço do caminho entre duas distâncias medidas desde a origem, com os cantos do meio.
// Usado no desmoronamento: o tracejado cresce das duas pontas para o meio.
export function trecho(caminho, de, ate) {
  const total = comprimento(caminho);
  const a = Math.max(0, Math.min(de, total));
  const b = Math.max(a, Math.min(ate, total));
  const inicio = pontoNoCaminho(caminho, a);
  const pontos = [[inicio.x, inicio.y]];
  let acumulado = 0;
  for (let i = 1; i < caminho.length - 1; i += 1) {
    acumulado += tamanho([caminho[i - 1], caminho[i]]);
    if (acumulado > a && acumulado < b) pontos.push([...caminho[i]]);
  }
  const fim = pontoNoCaminho(caminho, b);
  pontos.push([fim.x, fim.y]);
  return pontos;
}

function distanciaAoSegmento(px, py, [[x0, y0], [x1, y1]]) {
  const vx = x1 - x0;
  const vy = y1 - y0;
  const quadrado = vx * vx + vy * vy;
  const t = quadrado === 0 ? 0 : Math.max(0, Math.min(1, ((px - x0) * vx + (py - y0) * vy) / quadrado));
  return Math.hypot(px - (x0 + t * vx), py - (y0 + t * vy));
}

export function invadeEntrada(caminho, entrada, folga = FOLGA) {
  const limite = RAIO_ENTRADA + folga;
  return segmentos(caminho).some((s) => distanciaAoSegmento(entrada.x, entrada.y, s) < limite);
}

// Comprimento de [ini, fim] fora dos intervalos `tampas` (que podem se sobrepor).
function foraDasTampas(ini, fim, tampas) {
  const cortes = tampas
    .map(([a, b]) => [Math.max(a, ini), Math.min(b, fim)])
    .filter(([a, b]) => b > a)
    .sort((p, q) => p[0] - q[0]);
  let coberto = 0;
  let ate = ini;
  for (const [a, b] of cortes) {
    if (b <= ate) continue;
    coberto += b - Math.max(a, ate);
    ate = b;
  }
  return fim - ini - coberto;
}

// Quanto `a` e `b` correm juntos (segmentos colineares), fora das zonas das pontas comuns.
export function sobreposicao(a, b, zonas = []) {
  let total = 0;
  for (const sa of segmentos(a)) {
    for (const sb of segmentos(b)) {
      const [[ax0, ay0], [ax1, ay1]] = sa;
      const [[bx0, by0], [bx1, by1]] = sb;
      const horizontal = ay0 === ay1 && by0 === by1 && ay0 === by0 && ax0 !== ax1 && bx0 !== bx1;
      const vertical = ax0 === ax1 && bx0 === bx1 && ax0 === bx0 && ay0 !== ay1 && by0 !== by1;
      if (!horizontal && !vertical) continue;
      const [p0, p1, q0, q1, fixo] = horizontal ? [ax0, ax1, bx0, bx1, ay0] : [ay0, ay1, by0, by1, ax0];
      const ini = Math.max(Math.min(p0, p1), Math.min(q0, q1));
      const fim = Math.min(Math.max(p0, p1), Math.max(q0, q1));
      if (fim <= ini) continue;
      const tampas = zonas
        .map((z) => {
          const [centro, desvio] = horizontal ? [z.x, z.y - fixo] : [z.y, z.x - fixo];
          const meia = Math.sqrt(Math.max(0, ZONA * ZONA - desvio * desvio));
          return [centro - meia, centro + meia];
        })
        .filter(([lo, hi]) => hi > lo);
      total += foraDasTampas(ini, fim, tampas);
    }
  }
  return total;
}

export function caixaDoRotulo(no, lado, texto) {
  const w = texto.length * LARGURA_LETRA;
  const h = ALTURA_ROTULO;
  const { x, y } = no;
  const d = AFASTAMENTO;
  const g = AFASTAMENTO_DIAGONAL;
  const posicoes = {
    direita: [x + d, y - h / 2, "start"],
    esquerda: [x - d - w, y - h / 2, "end"],
    acima: [x - w / 2, y - d - h, "middle"],
    abaixo: [x - w / 2, y + d, "middle"],
    "acima-direita": [x + g, y - g - h, "start"],
    "acima-esquerda": [x - g - w, y - g - h, "end"],
    "abaixo-direita": [x + g, y + g, "start"],
    "abaixo-esquerda": [x - g - w, y + g, "end"],
  };
  const [x0, y0, ancora] = posicoes[lado] ?? posicoes.abaixo;
  const ancoraX = { start: x0, end: x0 + w, middle: x0 + w / 2 }[ancora];
  return { x0, y0, x1: x0 + w, y1: y0 + h, x: ancoraX, y: y0 + h - 4, ancora };
}

// O túnel (com meia largura `meia`) encosta na caixa?
export function cruzaCaixa(caminho, caixa, meia = 11) {
  return segmentos(caminho).some(([[x0, y0], [x1, y1]]) => {
    const sx0 = Math.min(x0, x1) - meia;
    const sx1 = Math.max(x0, x1) + meia;
    const sy0 = Math.min(y0, y1) - meia;
    const sy1 = Math.max(y0, y1) + meia;
    return sx0 < caixa.x1 && caixa.x0 < sx1 && sy0 < caixa.y1 && caixa.y0 < sy1;
  });
}
