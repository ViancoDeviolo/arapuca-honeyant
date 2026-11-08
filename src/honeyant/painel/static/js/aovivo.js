// Resumo ao vivo: funções puras, testadas com node --test.

export const MAXIMO_FORMIGAS_POR_CONSULTA = 6;

// Um serviço por ataque novo: a diferença do acumulado entre duas consultas.
// Contador que diminui (isca reiniciada) não solta formiga; no máximo `maximo` por vez.
export function novosAtaques(anterior, atual, maximo = MAXIMO_FORMIGAS_POR_CONSULTA) {
  if (!anterior) return [];
  const saida = [];
  for (const servico of Object.keys(atual).sort()) {
    const novos = (atual[servico] ?? 0) - (anterior[servico] ?? 0);
    for (let i = 0; i < novos && saida.length < maximo; i += 1) saida.push(servico);
  }
  return saida;
}

// Base para contar ataques novos: só uma resposta ao vivo. Depois de um período offline,
// a diferença para o cache seria o atraso acumulado, não ataques novos.
export function acumuladoParaComparar(resposta) {
  return resposta.origem === "ao_vivo" ? resposta.resumo.acumulado_por_servico : null;
}

function formatar(iso, fuso, opcoes) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: fuso, ...opcoes }).format(new Date(iso));
}

const DATA_E_HORA = { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" };

// Texto do cabeçalho para cada origem do resumo. `fuso` só nos testes: no navegador,
// o fuso da máquina de quem usa.
export function textoDaOrigem(r, fuso = undefined) {
  let texto;
  if (r.origem === "ao_vivo") {
    texto = `Ao vivo · atualizado às ${formatar(r.atualizado_em, fuso, { hour: "2-digit", minute: "2-digit" })}`;
  } else if (r.origem === "offline") {
    texto = `Resumo de ${formatar(r.atualizado_em, fuso, DATA_E_HORA).replace(",", "")}, offline`;
  } else if (r.origem === "real") {
    texto = `Ataques reais, congelados em ${formatar(r.resumo.gerado_em, fuso, DATA_E_HORA).replace(",", "")}`;
  } else {
    texto = "Dados de exemplo";
  }
  return r.aviso ? `${texto} · ${r.aviso}` : texto;
}
