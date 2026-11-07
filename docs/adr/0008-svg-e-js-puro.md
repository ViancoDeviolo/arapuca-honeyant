# ADR 0008 — SVG + JavaScript puro em vez de framework ou D3

- **Status:** aceito
- **Data:** 2026-11-06

## Contexto

O formigueiro é uma rede fixa de 8 entradas e 11 túneis, com até 20 formigas na tela. O
painel também mostra dados vindos de atacantes (senhas, países), que precisam de uma
política de segurança rígida.

## Decisão

- **SVG** desenhado por **módulos ES** sem dependência: `estado.js`, `geometria.js`,
  `comparativo.js`, `risco.js` (funções puras, testadas com `node --test`), `cena.js`
  (desenho e animação) e `app.js` (dados e eventos).
- Os traçados dos túneis ficam em `static/layout.json`, feitos à mão em grade ortogonal.
- **CSP** sem script nem estilo inline (`script-src 'self'`); dado externo só entra por
  `textContent`. Um teste varre todo `.js` atrás de `innerHTML`, `eval` e afins.
- Temas por variáveis CSS (`static/temas.css`).

## Alternativas consideradas

- **D3:** ótimo para grafos dinâmicos, mas a rede é fixa; seria uma dependência grande
  para pouco uso. Descartado (o spec exige ADR para trazê-lo).
- **React/Vue:** build, `node_modules` e mais superfície, para uma página. Descartado.
- **Three.js:** cena 3D sem necessidade, e mais uma dependência grande. Descartado.
- **Cena 2.5D em perspectiva (SVG):** foi a primeira versão; a grade ortogonal ficou mais
  legível no projetor. Trocada em 07/11.

## Consequências

- Nada para compilar: os arquivos estáticos são servidos como estão.
- A lógica que importa (largura dos túneis, comparativo, faixas de risco) tem teste.
- Desenhar uma rede nova exige ajustar o `layout.json` à mão.
