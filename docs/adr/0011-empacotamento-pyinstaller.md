# ADR 0011 — App de arquivo único com PyInstaller

- **Status:** aceito
- **Data:** 2026-11-07

## Contexto

A equipe e a banca precisam abrir o painel ao vivo nas próprias máquinas Windows, com dois
cliques, sem instalar Python, uv nem Docker. O app (`honeyant-app`) já existe em Python e
usa FastAPI, uvicorn, pydantic e o pathfinder (numpy, scipy, scikit-fuzzy).

## Decisão

- **PyInstaller 6.22.3**, versão fixada, rodado só no build com
  `uv run --with pyinstaller==6.22.3` (não entra nas dependências do projeto).
- `--onefile --console`: um `HoneyAnt.exe`; a janela de console mostra o estado
  ("ao vivo", "offline") e fechar a janela encerra o app.
- Embutidos: `docs/demo` (resumo real, perfis, replays), os estáticos do painel, o `app.json`
  com a URL do resumo-api e o **certificado público** da CA. Nunca a chave de acesso.
- Script: `infra/app/construir.ps1`. `build/`, `build-app/`, `dist/` e `*.spec` no `.gitignore`.
- Distribuição por link direto, só para a equipe e a banca; nunca no repositório nem em
  Releases.

## Alternativas consideradas

- **Nuitka:** compila para C e costuma gerar menos falso positivo no antivírus, mas precisa
  de um compilador C no Windows e o build demora; arriscado na véspera do congelamento.
- **zipapp / shiv:** um arquivo só, mas exige Python instalado na máquina de quem usa.
- **Instalador (MSI/Inno Setup):** mais "profissional", mas não é um arquivo único e pede
  permissão de administrador.

## Consequências

- **Sem assinatura de código.** O SmartScreen avisa "O Windows protegeu o computador" quando o
  arquivo vem da internet: "Mais informações" → "Executar assim mesmo".
- **Falsos positivos:** o carregador do `--onefile` às vezes é marcado pelo Defender. Se for
  colocado em quarentena, o **plano B** é rodar o painel pelo código-fonte:
  `uv run honeyant-local` (sem o ao vivo) — o README mantém esse caminho documentado.
- O `.exe` é grande (o pathfinder leva numpy e scipy) e demora alguns segundos para abrir,
  porque o `--onefile` extrai tudo numa pasta temporária a cada execução.
- `HONEYANT_SEM_NAVEGADOR=1` evita abrir o navegador (testes de fumaça do `.exe`).
- A chave de acesso fica em `%APPDATA%\HoneyAnt\config.json` em texto (dívida técnica:
  proteger com DPAPI).
