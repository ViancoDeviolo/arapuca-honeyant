// Seletor de tema: só visual. Guarda a escolha no navegador de quem está vendo;
// sem escolha salva, segue o sistema (claro → Papel, escuro → Noite).

export const TEMAS = Object.freeze({
  noite: "Noite",
  papel: "Papel",
  terra: "Terra",
  radar: "Radar",
  contraste: "Alto contraste",
});
export const CHAVE = "honeyant.tema";

export function temaInicial(salvo, prefereClaro) {
  if (Object.hasOwn(TEMAS, salvo)) return salvo;
  return prefereClaro ? "papel" : "noite";
}

function lerSalvo() {
  try { return localStorage.getItem(CHAVE); } catch { return null; }
}

function salvar(tema) {
  try { localStorage.setItem(CHAVE, tema); } catch { /* navegação privada: só não lembra */ }
}

function aplicar(tema) {
  document.documentElement.dataset.tema = tema;
  const nome = document.getElementById("nome-tema");
  if (nome) nome.textContent = TEMAS[tema];
  const radio = document.getElementById(`tema-${tema}`);
  if (radio) radio.checked = true;
}

if (typeof document !== "undefined") {
  const claro = window.matchMedia("(prefers-color-scheme: light)").matches;
  aplicar(temaInicial(lerSalvo(), claro));
  document.querySelectorAll('input[name="tema"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      aplicar(radio.value);
      salvar(radio.value);
    });
  });
}
