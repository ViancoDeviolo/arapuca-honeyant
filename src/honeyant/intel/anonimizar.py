"""Mascara IPv4 dentro de textos que vão sair da EC2 (usuário e senha tentados).

Scanners automatizados às vezes ecoam o IP do alvo no usuário, como em
`MGLNDD_<IPv4>_<porta>`. Esse IP é o da própria isca, não o de um atacante, mas nenhum IPv4
entra no repositório público: ele vira `<ipv4>` (ex.: `MGLNDD_<ipv4>_23`).
"""

import re

MASCARA = "<ipv4>"
_OCTETO = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
# Quatro octetos de 0 a 255, sem estar colado a outro dígito ou a mais um ".número"
# (assim 1.2.3.4.5, 999.1.1.1 e 10.0.0 ficam intactos).
_IPV4 = re.compile(rf"(?<![\d.]){_OCTETO}(?:\.{_OCTETO}){{3}}(?!\.?\d)")


def mascarar_ipv4(texto: str) -> str:
    return _IPV4.sub(MASCARA, texto)
