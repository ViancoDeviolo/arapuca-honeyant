"""Resumo ao vivo no app: cliente HTTPS do resumo-api (spec do aplicativo ao vivo, 3.3).

A conexão só confia na CA do projeto, confere o IP do servidor no certificado e exige
TLS 1.2 ou superior.
"""

import ssl
from pathlib import Path


def contexto_cliente(ca: Path) -> ssl.SSLContext:
    """Só a CA do projeto; nome (IP) conferido no SAN; TLS 1.2+."""
    contexto = ssl.create_default_context(cafile=str(ca))
    contexto.check_hostname = True
    contexto.verify_mode = ssl.CERT_REQUIRED
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    return contexto
