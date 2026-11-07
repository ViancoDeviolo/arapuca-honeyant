# ADR 0009 — Login do painel: scrypt, sessão no servidor e limites

- **Status:** aceito
- **Data:** 2026-11-07

## Contexto

O painel mostra dados da isca e controla a demonstração. No notebook ele fica preso a
127.0.0.1, mas o mesmo app deve poder ir para a nuvem. A senha não pode ficar em texto em
lugar nenhum.

## Decisão

- **Uma senha**, guardada só como hash **scrypt** com sal em `HONEYANT_PAINEL_SENHA_HASH`
  (gerado por `honeyant-hash-senha`). Hash inválido impede o painel de subir.
- **Sessão no servidor**: o cookie leva só um token aleatório (`HttpOnly`, `Secure`,
  `SameSite=Strict`, 8 h); o servidor guarda o *digest* do token e a validade.
- **Limites:** 5 falhas por IP em 15 min bloqueiam por 15 min; corpo do formulário
  limitado; `Origin` conferido no `POST /login` e no `POST /logout`.
- **Sem o hash**, o painel abre sem login, mas só em 127.0.0.1. Um teste roda o `main()` de
  verdade com o hash e exige 401 na API e redirecionamento na página.
- O login entra pelo **ponto de encaixe** (`Encaixe`) da fábrica do app: o painel não
  conhece o módulo de login.

## Alternativas consideradas

- **JWT:** sem estado no servidor, mas sem como revogar uma sessão ao sair. Descartado.
- **bcrypt/argon2:** bons, mas são dependências novas; o scrypt vem no `hashlib`.
- **OAuth:** exigiria saída de rede e um provedor externo. Descartado.

## Consequências

- Reiniciar o painel derruba as sessões (estão em memória).
- Várias instâncias na nuvem precisariam de um armazenamento de sessão compartilhado.
- O modo nuvem, quando existir, deve recusar subir sem o hash (dívida técnica no README).
