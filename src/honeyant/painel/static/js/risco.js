// Funções puras dos cartões da isca e dos dispositivos. Testadas com node --test.

// Faixas do spec do painel (5.2): < 0,3 baixo; < 0,6 médio; < 0,85 alto; senão crítico.
export function nivelDeRisco(r) {
  if (r < 0.3) return "baixo";
  if (r < 0.6) return "medio";
  if (r < 0.85) return "alto";
  return "critico";
}

export const ROTULO_NIVEL = { baixo: "Baixo", medio: "Médio", alto: "Alto", critico: "Crítico" };

// Sorteia um serviço na proporção das contagens (ex.: {telnet: 198, mqtt: 2}).
// `aleatorio` devolve um número em [0, 1), como Math.random; injetado para o teste.
export function sortearServico(porServico, aleatorio = Math.random) {
  const itens = Object.entries(porServico).filter(([, n]) => n > 0).sort(([a], [b]) => a.localeCompare(b));
  const total = itens.reduce((s, [, n]) => s + n, 0);
  if (total === 0) return null;
  let alvo = aleatorio() * total;
  for (const [servico, n] of itens) {
    if (alvo < n) return servico;
    alvo -= n;
  }
  return itens[itens.length - 1][0];
}

// Os N maiores de um objeto {chave: contagem}, maior primeiro; empate pela chave.
export function maiores(contagens, n) {
  return Object.entries(contagens)
    .sort(([a, x], [b, y]) => y - x || a.localeCompare(b))
    .slice(0, n);
}
