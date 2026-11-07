"""`honeyant-conferir-resumo`: confere o resumo-api da EC2 com o mesmo cliente do app.

    uv run honeyant-conferir-resumo --url https://<ip-elastico>

Pede a chave de acesso (sem mostrar na tela) e faz um `GET /api/v1/resumo` confiando só na
CA do projeto, conferindo o IP no certificado e exigindo TLS 1.2+. Serve no lugar do `curl`
do Windows, que não aceita IP no certificado.
"""

import argparse
import getpass
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from honeyant.apps.certificados import CA_PADRAO
from honeyant.apps.resumo_ao_vivo import contexto_cliente
from honeyant.core.resumo import ResumoDeAmeaca


def main(argv: Sequence[str] | None = None, chave: str | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="honeyant-conferir-resumo", description=__doc__.splitlines()[0]
    )
    p.add_argument("--url", required=True, help="https://<ip-elastico>")
    p.add_argument("--ca", type=Path, default=CA_PADRAO / "ca.crt")
    args = p.parse_args(argv)
    if not args.url.startswith("https://"):
        print("a URL precisa começar com https:// (a chave nunca vai em texto puro)")
        return 2
    chave = chave if chave is not None else getpass.getpass("Chave de acesso: ").strip()
    abridor = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),  # direto, como o app
        urllib.request.HTTPSHandler(context=contexto_cliente(args.ca)),
    )
    pedido = urllib.request.Request(  # noqa: S310  # só https, URL do próprio projeto
        f"{args.url.rstrip('/')}/api/v1/resumo", headers={"Authorization": f"Bearer {chave}"}
    )
    try:
        with abridor.open(pedido, timeout=10) as r:
            resumo = ResumoDeAmeaca.model_validate_json(r.read())
    except urllib.error.HTTPError as erro:
        print(f"{erro.code}: recusado (401 = chave errada; 429 = IP bloqueado por 15 min)")
        return 1
    except (urllib.error.URLError, OSError) as erro:
        print(f"sem conexão: {getattr(erro, 'reason', erro)}")
        return 1
    except ValidationError:
        print("200, mas a resposta não é um resumo válido")
        return 1
    print(f"200: resumo válido, {resumo.total_eventos} eventos nas últimas 24 h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
