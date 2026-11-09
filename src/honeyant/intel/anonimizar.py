"""Mascara IPv4 dentro de textos que vão sair da EC2 (usuário e senha tentados).

Scanners automatizados às vezes ecoam o IP do alvo no usuário, como em
`MGLNDD_<IPv4>_<porta>`. Esse IP é o da própria isca, não o de um atacante, mas nenhum IPv4
entra no repositório público: ele vira `<ipv4>` (ex.: `MGLNDD_<ipv4>_23`).

Privacidade vale mais que falso positivo. Por isso a máscara pega também:

- octetos com zeros à esquerda (`054.175.090.121`);
- IPv4 seguido de `.porta` ou de mais partes: `54.175.90.121.23` vira `<ipv4>.23`. Pela
  mesma regra, `1.2.3.4.5` (uma versão, um OID) vira `<ipv4>.5`: os quatro primeiros
  números têm cara de IPv4 e são mascarados;
- quatro octetos separados por hífen, como nos nomes de host da AWS
  (`ec2-54-175-90-121` vira `ec2-<ipv4>`). Datas como `2026-11-09` têm só três partes e
  ficam intactas.

Continua intacto o que não pode ser IPv4: octeto acima de 255 (`999.1.1.1`), só três
partes (`10.0.0`) e números colados a outro dígito (`12345.6.7.8`).
"""

import re

MASCARA = "<ipv4>"
# 0 a 255, com até três dígitos (aceita zeros à esquerda: 054, 090, 007).
_OCTETO = r"(?:25[0-5]|2[0-4]\d|1\d\d|0?\d?\d)"
# Pontos: quatro octetos sem dígito nem "." antes e sem dígito logo depois. Um ".23" (porta
# ou quinta parte) depois não impede a máscara.
_IPV4_PONTOS = re.compile(rf"(?<![\d.]){_OCTETO}(?:\.{_OCTETO}){{3}}(?!\d)")
# Hífens: a sequência inteira de grupos de 1 a 3 dígitos separados por "-", sem dígito nem
# "dígito-" antes e sem dígito depois. A escolha dos quatro octetos fica em `_hifens`.
_GRUPOS_COM_HIFEN = re.compile(r"(?<!\d)(?<!\d-)\d{1,3}(?:-\d{1,3}){3,}(?!\d)")


def _octeto_valido(parte: str) -> bool:
    return int(parte) <= 255


def _hifens(achado: re.Match[str]) -> str:
    """Mascara os primeiros quatro grupos seguidos que formam um IPv4 válido.

    Se o primeiro grupo está colado a uma letra e há mais de quatro grupos (o `2` de
    `ec2-54-175-90-121`), ele é o fim de uma palavra, não um octeto: a busca começa no
    seguinte.
    """
    partes = achado.group().split("-")
    colado_a_letra = achado.start() > 0 and achado.string[achado.start() - 1].isalpha()
    inicio = 1 if colado_a_letra and len(partes) > 4 else 0
    for i in range(inicio, len(partes) - 3):
        if all(_octeto_valido(p) for p in partes[i : i + 4]):
            return "-".join([*partes[:i], MASCARA, *partes[i + 4 :]])
    return achado.group()


def mascarar_ipv4(texto: str) -> str:
    return _GRUPOS_COM_HIFEN.sub(_hifens, _IPV4_PONTOS.sub(MASCARA, texto))
