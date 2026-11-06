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

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o [Código de Conduta](CODE_OF_CONDUCT.md).

## Licença

[MIT](LICENSE).

## Atribuições

IP Geolocation by DB-IP (https://db-ip.com), licença [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).
