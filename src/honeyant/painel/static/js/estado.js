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

// Quantas formigas da iteração passaram por cada túnel.
function trafego(caminhos) {
  const contagem = new Map();
  for (const nos of caminhos ?? []) {
    for (let i = 0; i + 1 < nos.length; i += 1) {
      const chave = `${nos[i]}->${nos[i + 1]}`;
      contagem.set(chave, (contagem.get(chave) ?? 0) + 1);
    }
  }
  return contagem;
}

// A largura segue o tráfego de formigas da iteração, não τ/τ_max: com os parâmetros do
// ACO (τ_max = 1, todas as formigas depositam), o feromônio satura no teto por volta da
// iteração 24 e todos os túneis ficariam iguais. O tráfego é guiado pelo feromônio e
// continua diferenciando os caminhos.
export function estadoDoTunel(chave, snapshot, analise) {
  const contagem = trafego(snapshot?.caminhos);
  const maximo = contagem.size ? Math.max(...contagem.values()) : 0;
  const brilho = maximo > 0 ? (contagem.get(chave) ?? 0) / maximo : 0;
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
