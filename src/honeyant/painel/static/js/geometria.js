// Geometria dos túneis: Bézier cúbica com pontos de controle do layout (spec do painel, 4.3).
// Funções puras: testadas com `node --test tests/js/`.

export const CAMARA_RX = 56;
export const CAMARA_RY = 34;
export const FOLGA = 12;

export function curvaDoTunel(origem, destino, layout) {
  const p0 = [origem.x, origem.y];
  const p3 = [destino.x, destino.y];
  const controles = layout[`${origem.id}->${destino.id}`];
  if (controles) return [p0, controles[0], controles[1], p3];
  const terco = (f) => [p0[0] + (p3[0] - p0[0]) * f, p0[1] + (p3[1] - p0[1]) * f];
  return [p0, terco(1 / 3), terco(2 / 3), p3];
}

export function pontoNaBezier(curva, t) {
  const u = 1 - t;
  const pesos = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t];
  let x = 0;
  let y = 0;
  curva.forEach(([px, py], i) => {
    x += pesos[i] * px;
    y += pesos[i] * py;
  });
  return [x, y];
}

export function invadeCamara(curva, camara, folga = FOLGA, amostras = 64) {
  const rx = CAMARA_RX + folga;
  const ry = CAMARA_RY + folga;
  for (let i = 0; i <= amostras; i += 1) {
    const t = 0.05 + (0.9 * i) / amostras;
    const [x, y] = pontoNaBezier(curva, t);
    const dx = (x - camara.x) / rx;
    const dy = (y - camara.y) / ry;
    if (dx * dx + dy * dy < 1) return true;
  }
  return false;
}
