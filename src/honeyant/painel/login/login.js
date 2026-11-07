"use strict";

// O servidor volta para /login?erro=1 quando a senha está errada.
// A mensagem entra só como texto (textContent).
const erro = document.getElementById("login-erro");
if (new URLSearchParams(location.search).get("erro") === "1") {
  erro.textContent = "Senha incorreta.";
  erro.hidden = false;
}
