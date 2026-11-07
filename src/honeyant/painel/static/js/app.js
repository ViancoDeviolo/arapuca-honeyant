// Ligação da página: busca os dados, controla o stream e atualiza a cena e os textos.
// Dado da casa ou da isca só entra no DOM por textContent.

import { aceitarSnapshot } from "./estado.js";
import { criarCena } from "./cena.js";

const $ = (id) => document.getElementById(id);
const SESSAO_EXPIRADA = "Sessão expirada. Entre de novo.";
const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

class SessaoExpirada extends Error {}

async function buscar(url) {
  const r = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (r.status === 401 || r.status === 403) throw new SessaoExpirada();
  if (!r.ok) throw new Error(`${url} respondeu ${r.status}`);
  return r.json();
}

function avisar(texto) {
  $("status").textContent = texto;
}

function velocidade() {
  const marcado = document.querySelector('input[name="velocidade"]:checked');
  return marcado ? marcado.value : "1";
}

function dataCurta(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(d);
}

function mostrarOrigem(resumo) {
  $("atualizado").textContent =
    resumo.origem === "real"
      ? `Ataques reais, congelados em ${dataCurta(resumo.resumo.gerado_em)}`
      : "Dados de exemplo";
}

function pontoFraco(analise) {
  let melhor = null;
  for (const [chave, risco] of Object.entries(analise.riscos)) {
    if (melhor === null || risco > melhor[1]) melhor = [chave, risco];
  }
  return melhor ? melhor[0].split("->") : null;
}

function mostrarRota(analise, rotulos) {
  const lista = $("passos");
  lista.replaceChildren();
  const fraco = $("ponto-fraco");
  if (!analise.rota) {
    fraco.textContent = "Nenhuma rota até a fechadura.";
    $("anuncio").textContent = "Nenhuma rota até a fechadura.";
    return;
  }
  const [deFraco, paraFraco] = pontoFraco(analise) ?? [];
  analise.rota.nos.forEach((id, i, nos) => {
    const li = document.createElement("li");
    li.textContent = rotulos[id] ?? id;
    const noFraco = (id === deFraco && nos[i + 1] === paraFraco) || (id === paraFraco && nos[i - 1] === deFraco);
    if (noFraco) li.classList.add("passo-fraco");
    lista.appendChild(li);
  });
  const nomes = analise.rota.nos.map((id) => rotulos[id] ?? id).join(", ");
  const textoFraco = deFraco ? `Ponto fraco: ${rotulos[deFraco]} para ${rotulos[paraFraco]}.` : "";
  fraco.textContent = textoFraco;
  $("anuncio").textContent = `Rota prevista: ${nomes}. ${textoFraco}`.trim();
}

async function iniciar() {
  const perfil = "inseguro";
  const [casa, rotas, layout, resumo] = await Promise.all([
    buscar(`/api/v1/casa?perfil=${perfil}`),
    buscar("/api/v1/rotas"),
    buscar("/static/layout.json"),
    buscar("/api/v1/resumo"),
  ]);
  const analise = rotas[perfil];
  const rotulos = Object.fromEntries(casa.nos.map((n) => [n.id, n.rotulo]));
  const cena = criarCena($("formigueiro"), casa, layout, { reduzido });
  mostrarOrigem(resumo);
  cena.limpar(analise);
  $("passos").replaceChildren();
  $("ponto-fraco").textContent = "Clique em Prever invasão para ver a rota.";

  let fonte = null;
  let atual = null;
  let ultimo = null;

  function fecharStream() {
    if (fonte) fonte.close();
    fonte = null;
  }

  $("prever").addEventListener("click", () => {
    fecharStream();
    atual = null;
    ultimo = null;
    cena.limpar(analise);
    avisar("As formigas estão explorando a casa…");
    const params = new URLSearchParams({ perfil, modo: "prever", semente: "42", velocidade: velocidade() });
    const es = new EventSource(`/api/v1/formigueiro/stream?${params}`);
    fonte = es;
    es.addEventListener("snapshot", (ev) => {
      if (es !== fonte) return;
      const s = JSON.parse(ev.data);
      if (!aceitarSnapshot(atual, s)) return;
      atual = atual ?? s;
      ultimo = s;
      // Durante a exploração, só os túneis; a rota oficial (Dijkstra) aparece no fim.
      cena.aplicar(s, { rota: null, bloqueadas: analise.bloqueadas });
      avisar(`Iteração ${s.iteracao + 1}: as formigas reforçam os túneis mais fracos.`);
    });
    es.addEventListener("fim", () => {
      if (es !== fonte) return;
      fecharStream();
      if (ultimo) cena.aplicar(ultimo, analise);
      mostrarRota(analise, rotulos);
      avisar("Exploração concluída. A rota prevista está destacada em âmbar.");
    });
    es.addEventListener("error", async () => {
      if (es !== fonte) return;
      fecharStream();
      try {
        await buscar(`/api/v1/casa?perfil=${perfil}`);
        avisar("A conexão caiu. Clique em Prever invasão para tentar de novo.");
      } catch (erro) {
        avisar(erro instanceof SessaoExpirada ? SESSAO_EXPIRADA : "O painel não respondeu. Confira se ele está rodando.");
      }
    });
  });

  $("prever").disabled = false;
  avisar("Pronto. Clique em Prever invasão.");

  if (!reduzido) {
    const quadro = (agora) => {
      cena.animar(agora);
      requestAnimationFrame(quadro);
    };
    requestAnimationFrame(quadro);
  }
}

iniciar().catch((erro) => {
  avisar(erro instanceof SessaoExpirada ? SESSAO_EXPIRADA : "Não foi possível carregar a casa. Recarregue a página.");
});
