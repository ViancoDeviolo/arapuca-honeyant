"""Fuzzy de intenção do atacante (spec-mãe, seção 5): varredura, força bruta ou botnet.

Sistema pequeno e separado do fuzzy de arestas do pathfinder, em Python puro: o intel
roda na imagem da isca, que não leva numpy nem scikit-fuzzy.

Entradas, calculadas por origem dentro da janela (o IP fica só em memória):
- **diversidade**: quantos pares usuário/senha diferentes a origem tentou;
- **comandos**: média de comandos por sessão depois do login;
- **taxa**: sessões por hora.

Regras (mínimo para E, máximo para OU, complemento para NÃO):
1. comandos MUITOS                                         → botnet
2. diversidade ALTA e comandos NÃO muitos                  → força bruta
3. taxa ALTA e comandos NÃO muitos                         → força bruta
4. diversidade BAIXA e comandos NÃO muitos e taxa NÃO alta → varredura

Vence a saída de maior grau. Empate: a mais grave (botnet > força bruta > varredura).
"""

from honeyant.core.resumo import Intencao


def _subida(x: float, a: float, b: float) -> float:
    """0 até `a`, sobe em linha reta, 1 a partir de `b`."""
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    return (x - a) / (b - a)


def _descida(x: float, a: float, b: float) -> float:
    return 1.0 - _subida(x, a, b)


def graus(diversidade: float, comandos: float, taxa: float) -> dict[Intencao, float]:
    div_baixa, div_alta = _descida(diversidade, 1, 3), _subida(diversidade, 2, 6)
    cmd_muitos = _subida(comandos, 0.5, 3)
    taxa_alta = _subida(taxa, 10, 30)
    nao_muitos = 1 - cmd_muitos
    return {
        Intencao.BOTNET: cmd_muitos,
        Intencao.FORCA_BRUTA: max(min(div_alta, nao_muitos), min(taxa_alta, nao_muitos)),
        Intencao.VARREDURA: min(div_baixa, nao_muitos, 1 - taxa_alta),
    }


_GRAVIDADE = {Intencao.VARREDURA: 0, Intencao.FORCA_BRUTA: 1, Intencao.BOTNET: 2}


def classificar(diversidade: float, comandos: float, taxa: float) -> Intencao:
    g = graus(diversidade, comandos, taxa)
    return max(g, key=lambda i: (g[i], _GRAVIDADE[i]))
