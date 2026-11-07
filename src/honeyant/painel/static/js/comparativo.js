// Texto do cartão "Antes e depois" (spec do painel, 5.2). Função pura, testada com node --test.
// razão = plausibilidade antes / plausibilidade depois (plausibilidade = e^-custo).

export function formatarComparativo(antes, depois) {
  if (!depois) return { titulo: "nenhuma rota até a fechadura", razao: null };
  const razao = antes.plausibilidade / depois.plausibilidade;
  if (razao >= 2) return { titulo: `${Math.round(razao)}× menos plausível`, razao };
  if (razao >= 1) return { titulo: `${Math.round((1 - 1 / razao) * 100)}% menos plausível`, razao };
  // A mitigação nunca deveria facilitar a invasão; se facilitar, o cartão diz isso.
  return { titulo: `${Math.round((razao > 0 ? 1 / razao - 1 : 0) * 100)}% mais plausível`, razao };
}
