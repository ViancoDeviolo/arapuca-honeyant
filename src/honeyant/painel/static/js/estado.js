// Conversão de snapshot + análise em estado de desenho do túnel (spec do painel, 4.3).
// Funções puras: testadas com `node --test tests/js/`.

export const LARGURA_MIN = 4;
export const LARGURA_MAX = 22;

function arestasDaRota(analise) {
  const nos = analise?.rota?.nos ?? [];
  const chaves = new Set();
  for (let i = 0; i + 1 < nos.length; i += 1) chaves.add(`${nos[i]}->${nos[i + 1]}`);
  return chaves;
}

export function estadoDoTunel(chave, snapshot, analise) {
  const feromonio = snapshot?.feromonio ?? {};
  const valores = Object.values(feromonio);
  const tauMax = valores.length ? Math.max(...valores) : 0;
  const tau = feromonio[chave];
  const brilho = tau !== undefined && tauMax > 0 ? tau / tauMax : 0;
  return {
    largura: LARGURA_MIN + (LARGURA_MAX - LARGURA_MIN) * brilho,
    brilho,
    rota: arestasDaRota(analise).has(chave),
    bloqueado: (analise?.bloqueadas ?? []).includes(chave),
  };
}

// Só aceita snapshots da execução corrente: um stream antigo nunca se mistura ao novo.
export function aceitarSnapshot(atual, novo) {
  return atual === null || atual === undefined || novo.execucao_id === atual.execucao_id;
}
