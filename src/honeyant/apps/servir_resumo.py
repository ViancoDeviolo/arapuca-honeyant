"""`honeyant-servir-resumo`: o resumo-api da EC2 (spec do aplicativo ao vivo, seção 3.1).

Roda no container `resumo-api` (usuário 10002, banco em `mode=ro`), escutando em 8443; o
compose mapeia 443:8443. Variáveis:

    HONEYANT_DB                  banco da isca (padrão /dados/isca.db)
    HONEYANT_RESUMO_CHAVE_HASH   hash da chave de acesso (honeyant-chave-app). Obrigatório.
    HONEYANT_RESUMO_CERT         certificado do servidor (padrão /certs/servidor.crt)
    HONEYANT_RESUMO_CERT_CHAVE   chave do certificado (padrão /certs/servidor.key)

Sem o hash, o serviço recusa subir: na nuvem o acesso por chave é obrigatório.
"""

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.intel.acesso import ControleDeAcesso
from honeyant.intel.adapters.servidor_resumo import contexto_servidor, criar_servidor
from honeyant.intel.adapters.sqlite_leitura import LeitorSqlite
from honeyant.intel.resumo import agregar

PORTA = 8443
JANELA_HORAS = 24


def fonte_do_banco(caminho: Path) -> Callable[[], ResumoDeAmeaca]:
    """Abre o banco em mode=ro a cada cálculo (o cache do servidor limita a 1 a cada 15 s)."""

    def calcular() -> ResumoDeAmeaca:
        agora = datetime.now(UTC).replace(microsecond=0)
        leitor = LeitorSqlite(caminho)
        try:
            eventos = leitor.eventos_desde(agora - timedelta(hours=JANELA_HORAS))
            return agregar(eventos, leitor.acumulado_por_servico(), agora, JANELA_HORAS)
        finally:
            leitor.fechar()

    return calcular


def _sair(mensagem: str) -> None:
    print(f"erro: {mensagem}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    hash_salvo = os.environ.get("HONEYANT_RESUMO_CHAVE_HASH", "").strip()
    if not hash_salvo:
        _sair("HONEYANT_RESUMO_CHAVE_HASH não definida; gere com `uv run honeyant-chave-app`")
    try:
        acesso = ControleDeAcesso(hash_salvo)
    except ValueError as erro:
        _sair(str(erro))
    cert = Path(os.environ.get("HONEYANT_RESUMO_CERT", "/certs/servidor.crt"))
    chave = Path(os.environ.get("HONEYANT_RESUMO_CERT_CHAVE", "/certs/servidor.key"))
    banco = Path(os.environ.get("HONEYANT_DB", "/dados/isca.db"))
    servidor = criar_servidor(
        "0.0.0.0",  # noqa: S104  # nosec B104  # dentro do container; o Security Group restringe a 443
        PORTA,
        fonte_do_banco(banco),
        acesso,
        contexto_servidor(cert, chave),
    )
    print(f'{{"acao": "resumo-api iniciado", "porta": {PORTA}}}', file=sys.stderr, flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
