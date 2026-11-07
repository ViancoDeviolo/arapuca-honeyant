# ADR 0007 — Server-Sent Events em vez de WebSocket

- **Status:** aceito
- **Data:** 2026-11-06

## Contexto

O painel mostra o ACO iteração a iteração: o servidor manda snapshots, o navegador só
desenha. O cliente nunca precisa mandar nada pelo mesmo canal.

## Decisão

- **SSE** (`EventSource`) em `GET /api/v1/formigueiro/stream`, com eventos `snapshot` e `fim`.
- Parâmetros validados no servidor (`perfil`, `modo`, `velocidade` de 0,25 a 4, `semente`);
  nenhum parâmetro do ACO vem do cliente.
- No máximo um snapshot a cada 150 ms e **um stream por cliente** ("o mais novo vence").

## Alternativas consideradas

- **WebSocket:** bidirecional, que não usamos; exige outro protocolo, outra autenticação
  e mais código no servidor e no cliente. Descartado.
- **Polling:** simples, mas com atraso e requisições à toa. Descartado.

## Consequências

- O SSE é HTTP comum: passa pelo mesmo login (cookie de sessão), pela mesma CSP e pelo
  mesmo `TrustedHost` do resto da API.
- O navegador reconecta sozinho; o painel trata o erro e mostra uma mensagem.
