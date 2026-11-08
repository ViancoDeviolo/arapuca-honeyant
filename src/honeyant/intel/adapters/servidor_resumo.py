"""Servidor HTTPS do resumo ao vivo (spec do aplicativo ao vivo, seção 3.1).

Biblioteca padrão (`http.server` + `ssl`): a imagem da isca não tem FastAPI.

- Só `GET /api/v1/resumo`. Qualquer outra rota ou método: `404` sem corpo.
- `Authorization: Bearer <chave>` conferido pelo `ControleDeAcesso` (5 erros/15 min).
- Resumo guardado em memória por 15 s; banco indisponível dá `503` sem corpo.
- Cabeçalho `Server: honeyant`, sem versão. Log em JSON, sem a chave nem o cabeçalho.
"""

import json
import sqlite3
import ssl
import sys
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.intel.acesso import ControleDeAcesso

ROTA = "/api/v1/resumo"
# ValueError cobre a linha que não valida no contrato (ValidationError é um ValueError).
_FALHAS_DO_BANCO = (sqlite3.Error, FileNotFoundError, OSError, ValueError)


def contexto_servidor(cert: Path, chave: Path) -> ssl.SSLContext:
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    contexto.load_cert_chain(certfile=str(cert), keyfile=str(chave))
    return contexto


class _Cache:
    def __init__(self, fonte: Callable[[], ResumoDeAmeaca], validade_s: float, relogio) -> None:
        self._fonte, self._validade, self._relogio = fonte, validade_s, relogio
        self._corpo: bytes | None = None
        self._quando = 0.0
        self._trava = threading.Lock()

    def corpo(self) -> bytes:
        with self._trava:
            agora = self._relogio()
            if self._corpo is None or agora - self._quando >= self._validade:
                self._corpo = self._fonte().model_dump_json().encode("utf-8")
                self._quando = agora
            return self._corpo


def criar_servidor(
    endereco: str,
    porta: int,
    fonte: Callable[[], ResumoDeAmeaca],
    acesso: ControleDeAcesso,
    contexto_tls: ssl.SSLContext | None,
    cache_s: float = 15,
    relogio: Callable[[], float] = time.monotonic,
    timeout_conexao_s: float = 10,
) -> ThreadingHTTPServer:
    """`contexto_tls=None` só nos testes: em produção o `main` sempre passa o TLS."""
    cache = _Cache(fonte, cache_s, relogio)

    class Manipulador(BaseHTTPRequestHandler):
        server_version = "honeyant"
        sys_version = ""
        timeout = timeout_conexao_s
        protocol_version = "HTTP/1.0"

        def _responder(self, status: int, corpo: bytes = b"") -> None:
            self._status = status
            self.send_response_only(status)
            self.send_header("Server", self.server_version)
            self.send_header("Content-Length", str(len(corpo)))
            if corpo:
                self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if corpo:
                self.wfile.write(corpo)

        def send_error(self, code, message=None, explain=None):  # noqa: ARG002
            self._responder(code if code != 501 else 404)

        def do_GET(self) -> None:  # noqa: N802
            inicio = time.monotonic()
            if self.path != ROTA:
                self._responder(404)
            else:
                veredito = acesso.verificar(
                    self.client_address[0], self.headers.get("Authorization")
                )
                if veredito == "bloqueado":
                    self._responder(429)
                elif veredito == "negado":
                    self._responder(401)
                else:
                    try:
                        self._responder(200, cache.corpo())
                    except _FALHAS_DO_BANCO:
                        self._responder(503)
            self._registrar(inicio)

        def _nao_existe(self) -> None:
            inicio = time.monotonic()
            self._responder(404)
            self._registrar(inicio)

        do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _nao_existe  # noqa: N815

        def _registrar(self, inicio: float) -> None:
            linha = {
                "status": getattr(self, "_status", 0),
                "rota": self.path.split("?", 1)[0][:100],
                "ms": round((time.monotonic() - inicio) * 1000, 1),
            }
            print(json.dumps(linha), file=sys.stderr, flush=True)

        def log_message(self, format, *args) -> None:  # noqa: A002
            pass  # o registro é o _registrar: sem cabeçalhos, sem a chave

    class Servidor(ThreadingHTTPServer):
        def handle_error(self, request, client_address) -> None:  # noqa: ARG002
            # Handshake quebrado, HTTP puro na porta TLS, cliente que sumiu: uma linha
            # JSON, sem traceback e sem o IP do cliente.
            tipo = type(sys.exc_info()[1]).__name__
            print(json.dumps({"erro": "conexao", "tipo": tipo}), file=sys.stderr, flush=True)

    servidor = Servidor((endereco, porta), Manipulador)
    servidor.daemon_threads = True
    if contexto_tls is not None:
        # Handshake só na primeira leitura, já no thread da conexão e sob o timeout de
        # 10 s. Com o padrão (handshake dentro do accept()), um cliente que conecta e não
        # manda nada travava o servidor inteiro.
        servidor.socket = contexto_tls.wrap_socket(
            servidor.socket, server_side=True, do_handshake_on_connect=False
        )
    return servidor
