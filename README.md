# Arapuca HoneyAnt

> Roteadores avisam "você foi atacado". O HoneyAnt avisa "é por aqui que vão te invadir, com base no que os hackers estão fazendo agora — feche isso primeiro".

Ferramenta open source de segurança para casas inteligentes:

- uma **isca de baixa interação** na nuvem (Telnet e MQTT falsos) registra ataques reais da internet;
- um **gêmeo digital** de uma casa simulada em Docker recebe um resumo anonimizado desses ataques;
- um **sensor de tráfego** identifica vulnerabilidades na casa;
- **lógica fuzzy** transforma as evidências em risco por ligação entre dispositivos;
- um **algoritmo de colônia de formigas (ACO)** prevê o caminho de invasão mais plausível até a fechadura.

O nome junta *arapuca* (armadilha brasileira) e *honeypot ant* (formiga-pote-de-mel).

**Status:** em construção. O design está em [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Como rodar os testes

Requisitos: [uv](https://docs.astral.sh/uv/) (ele instala o Python 3.12 automaticamente).

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Painel local e login

```bash
uv run honeyant-hash-senha            # pede a senha e imprime o hash (nunca a senha)
# PowerShell: $env:HONEYANT_PAINEL_SENHA_HASH = "<hash>"
export HONEYANT_PAINEL_SENHA_HASH="<hash>"
uv run honeyant-local                 # http://127.0.0.1:8000
```

Com `HONEYANT_PAINEL_SENHA_HASH`, a página e a API exigem login (botão **Sair** no topo).
Sem ela, o painel abre sem login, mas só aceita conexões da própria máquina (127.0.0.1).
Um hash inválido impede o painel de subir. O cookie de sessão é `Secure` por padrão; se o
navegador recusar o cookie em `http://127.0.0.1`, use `HONEYANT_PAINEL_COOKIE_SEGURO=0`.

## Dívidas técnicas conhecidas

- **Modo nuvem do painel:** ainda não existe. Quando existir, ele deve **recusar subir sem
  `HONEYANT_PAINEL_SENHA_HASH`** (no modo local, o loopback é a proteção).

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o [Código de Conduta](CODE_OF_CONDUCT.md).

## Licença

[MIT](LICENSE).

## Atribuições

IP Geolocation by DB-IP (https://db-ip.com), licença [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).
