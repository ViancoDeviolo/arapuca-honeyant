"""Nenhum código desliga a verificação de TLS (spec do aplicativo ao vivo, seção 6)."""

import re
from pathlib import Path

SRC = Path(__file__).parents[2] / "src"
PROIBIDOS = re.compile(r"verify\s*=\s*False|check_hostname\s*=\s*False|CERT_NONE")


def test_nenhum_codigo_desliga_a_verificacao_de_tls():
    achados = [
        f"{arquivo.relative_to(SRC)}:{n}"
        for arquivo in SRC.rglob("*.py")
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1)
        if PROIBIDOS.search(linha)
    ]
    assert achados == []
