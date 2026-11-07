"""Login do painel: hash, bloqueio por tentativas, sessões, proteções e router.

Só stdlib, `fastapi` e `starlette`: não importa outros módulos do projeto e não lê o ambiente
(quem lê é `apps/painel_login.py`). Tudo entra por parâmetro: o hash, o relógio e os limites.

Decisões:
- hash com `hashlib.scrypt` (KDF de memória dura, stdlib, sem dependência nova), no formato
  `scrypt$n$r$p$<sal_b64>$<hash_b64>`, com os parâmetros no próprio valor;
- senha comparada com `hmac.compare_digest`;
- 5 falhas por IP dentro de 15 min bloqueiam por 15 min; durante o bloqueio a senha nem é
  verificada;
- sessão com `secrets.token_urlsafe(32)`, 8 h, guardada só como SHA-256;
- CSRF: `SameSite=Strict`, só `POST` e `Origin` (quando presente) de loopback.

Dívida técnica declarada: bloqueios e sessões ficam em memória. Reiniciar o processo limpa o
bloqueio (útil na demo) e derruba todas as sessões.
"""

import base64
import binascii
import hashlib
import hmac
import logging
import math
import secrets
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, params
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, Response

log = logging.getLogger("honeyant.painel.autenticacao")

Relogio = Callable[[], float]

COOKIE = "honeyant_sessao"
PASTA_LOGIN = Path(__file__).parent / "login"

_N, _R, _P, _DKLEN, _TAMANHO_SAL = 16384, 8, 1, 32, 16
_N_MIN, _N_MAX = 2**10, 2**17
_R_MAX, _P_MAX = 16, 4
_SENHA_MAX = 1024  # acima disso nem calculamos o hash
_CORPO_MAX = 4096
_TOKEN_MAX = 128
_HOSTS_DE_ORIGEM = frozenset({"127.0.0.1", "localhost", "::1"})
_SEM_CACHE = {"Cache-Control": "no-store"}


# --- 3.1 hash ----------------------------------------------------------------------


def _scrypt(senha: str, sal: bytes, n: int, r: int, p: int, tamanho: int) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"),
        salt=sal,
        n=n,
        r=r,
        p=p,
        dklen=tamanho,
        maxmem=2 * 128 * r * (n + p + 2),
    )


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(senha: str, *, sal: bytes | None = None) -> str:
    sal = secrets.token_bytes(_TAMANHO_SAL) if sal is None else sal
    h = _scrypt(senha, sal, _N, _R, _P, _DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(h)}"


def _decompor(salvo: str) -> tuple[int, int, int, bytes, bytes] | None:
    """Lê o hash; devolve None se estiver malformado ou com parâmetros fora dos limites."""
    partes = salvo.split("$") if isinstance(salvo, str) else []
    if len(partes) != 6 or partes[0] != "scrypt":
        return None
    numeros = partes[1:4]
    if not all(t.isascii() and t.isdigit() and len(t) <= 10 for t in numeros):
        return None
    n, r, p = (int(t) for t in numeros)
    if not (_N_MIN <= n <= _N_MAX and n & (n - 1) == 0):
        return None  # n gigante num hash adulterado travaria o servidor
    if not (1 <= r <= _R_MAX and 1 <= p <= _P_MAX):
        return None
    try:
        sal = base64.b64decode(partes[4], validate=True)
        esperado = base64.b64decode(partes[5], validate=True)
    except (binascii.Error, ValueError):
        return None
    if not (8 <= len(sal) <= 64 and 16 <= len(esperado) <= 64):
        return None
    return n, r, p, sal, esperado


def hash_valido(salvo: str) -> bool:
    return _decompor(salvo) is not None


def verificar_senha(senha: str, hash_salvo: str) -> bool:
    """Recalcula com os parâmetros do próprio hash. Hash malformado dá False, sem exceção."""
    partes = _decompor(hash_salvo)
    if partes is None or len(senha) > _SENHA_MAX:
        return False
    n, r, p, sal, esperado = partes
    return hmac.compare_digest(_scrypt(senha, sal, n, r, p, len(esperado)), esperado)


# --- 3.2 bloqueio por tentativas ---------------------------------------------------


class _Entrada:
    __slots__ = ("bloqueado_ate", "falhas")

    def __init__(self) -> None:
        self.falhas: deque[float] = deque()
        self.bloqueado_ate = 0.0


class LimiteDeTentativas:
    """`maximo` falhas dentro de `janela_s` bloqueiam o IP por `janela_s`.

    Na demo todo acesso vem de 127.0.0.1: errar `maximo` vezes bloqueia o próprio apresentador.
    O bloqueio fica só em memória, então reiniciar o processo o limpa.
    """

    def __init__(
        self,
        maximo: int = 5,
        janela_s: int = 900,
        relogio: Relogio = time.monotonic,
        teto_de_ips: int = 4096,
    ) -> None:
        self._maximo = maximo
        self._janela_s = janela_s
        self._relogio = relogio
        self._teto = teto_de_ips
        self._entradas: OrderedDict[str, _Entrada] = OrderedDict()

    @property
    def tamanho(self) -> int:
        return len(self._entradas)

    def bloqueado(self, ip: str) -> float:
        """Segundos que faltam para o fim do bloqueio (0 se o IP está livre)."""
        entrada = self._entradas.get(ip)
        if entrada is None or not entrada.bloqueado_ate:
            return 0
        restante = entrada.bloqueado_ate - self._relogio()
        if restante > 0:
            return restante
        del self._entradas[ip]
        return 0

    def falhou(self, ip: str) -> None:
        agora = self._relogio()
        entrada = self._entradas.get(ip)
        if entrada is None:
            while len(self._entradas) >= self._teto:
                self._entradas.popitem(last=False)  # descarta o IP mais antigo
            entrada = self._entradas[ip] = _Entrada()
        while entrada.falhas and agora - entrada.falhas[0] >= self._janela_s:
            entrada.falhas.popleft()
        entrada.falhas.append(agora)
        if len(entrada.falhas) >= self._maximo:
            entrada.bloqueado_ate = agora + self._janela_s
        self._entradas.move_to_end(ip)

    def acertou(self, ip: str) -> None:
        self._entradas.pop(ip, None)


# --- 3.3 sessões -------------------------------------------------------------------


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _token_plausivel(token: str | None) -> bool:
    return bool(token) and len(token) <= _TOKEN_MAX and token.isascii()


class Sessoes:
    """Sessões em memória. O servidor guarda só o SHA-256 do token."""

    def __init__(
        self, validade_s: int = 8 * 3600, relogio: Relogio = time.monotonic, teto: int = 32
    ) -> None:
        self._validade_s = validade_s
        self._relogio = relogio
        self._teto = teto
        self._expira_em: OrderedDict[str, float] = OrderedDict()

    @property
    def tamanho(self) -> int:
        return len(self._expira_em)

    def criar(self) -> str:
        agora = self._relogio()
        for chave in [c for c, t in self._expira_em.items() if t <= agora]:
            del self._expira_em[chave]
        while len(self._expira_em) >= self._teto:
            self._expira_em.popitem(last=False)
        token = secrets.token_urlsafe(32)
        self._expira_em[_digest(token)] = agora + self._validade_s
        return token

    def valida(self, token: str | None) -> bool:
        if not _token_plausivel(token):
            return False
        chave = _digest(token)
        expira = self._expira_em.get(chave)
        if expira is None:
            return False
        if self._relogio() >= expira:
            del self._expira_em[chave]
            return False
        return True

    def encerrar(self, token: str | None) -> None:
        if _token_plausivel(token):
            self._expira_em.pop(_digest(token), None)


# --- 3.4 dependências de proteção --------------------------------------------------


def criar_protecoes(sessoes: Sessoes) -> tuple[params.Depends, params.Depends]:
    """(proteção da API, proteção da página): 401 e 303 para `/login`, respectivamente."""

    async def api(request: Request) -> None:
        if not sessoes.valida(request.cookies.get(COOKIE)):
            raise HTTPException(status_code=401, detail="Não autenticado.")

    async def pagina(request: Request) -> None:
        if not sessoes.valida(request.cookies.get(COOKIE)):
            raise HTTPException(status_code=303, headers={"Location": "/login"})

    return Depends(api), Depends(pagina)


# --- 3.5 router do login -----------------------------------------------------------


def _origem_permitida(request: Request) -> bool:
    """Sem `Origin` passa; com `Origin`, só loopback (compara o host e ignora a porta)."""
    origem = request.headers.get("origin")
    if origem is None:
        return True
    try:
        partes = urlsplit(origem)
        return partes.scheme in {"http", "https"} and partes.hostname in _HOSTS_DE_ORIGEM
    except ValueError:
        return False


async def _ler_corpo(request: Request) -> bytes | None:
    """Lê até 4 KB por stream; None se passar disso (o corpo não é bufferizado inteiro)."""
    try:
        if int(request.headers.get("content-length") or 0) > _CORPO_MAX:
            return None
    except ValueError:
        return None
    dados = bytearray()
    async for pedaco in request.stream():
        dados += pedaco
        if len(dados) > _CORPO_MAX:
            return None
    return bytes(dados)


def criar_router_login(
    hash_salvo: str, sessoes: Sessoes, limite: LimiteDeTentativas, *, cookie_seguro: bool = True
) -> APIRouter:
    if not hash_valido(hash_salvo):
        raise ValueError("o hash da senha do painel é inválido (gere com honeyant-hash-senha)")
    router = APIRouter()

    def _arquivo(nome: str) -> FileResponse:
        # Caminho fixo no código: nada da URL entra na montagem.
        return FileResponse(PASTA_LOGIN / nome, headers=_SEM_CACHE)

    @router.get("/login", include_in_schema=False)
    def formulario() -> FileResponse:
        return _arquivo("login.html")

    @router.get("/login/login.css", include_in_schema=False)
    def estilo() -> FileResponse:
        return _arquivo("login.css")

    @router.get("/login/login.js", include_in_schema=False)
    def script() -> FileResponse:
        return _arquivo("login.js")

    @router.post("/login", include_in_schema=False)
    async def entrar(request: Request) -> Response:
        if not _origem_permitida(request):
            return PlainTextResponse("Origem não permitida.", status_code=403)
        corpo = await _ler_corpo(request)
        if corpo is None:
            return PlainTextResponse("Corpo grande demais.", status_code=413)
        ip = request.client.host if request.client else "desconhecido"

        restante = limite.bloqueado(ip)
        if restante > 0:  # bloqueado: nem verifica a senha
            minutos = max(1, math.ceil(restante / 60))
            return PlainTextResponse(
                f"Muitas tentativas. Tente de novo em {minutos} min.",
                status_code=429,
                headers={"Retry-After": str(math.ceil(restante))},
            )

        try:
            campos = parse_qs(corpo.decode("utf-8", "replace"), max_num_fields=8)
        except ValueError:
            campos = {}
        senha = (campos.get("senha") or [""])[0]
        # Sem `await` entre a checagem de bloqueio e `falhou`: requisições simultâneas não
        # furam o limite (o hash roda no próprio loop, ~50 ms por tentativa).
        if not verificar_senha(senha, hash_salvo):
            limite.falhou(ip)
            log.warning("falha de login")
            return RedirectResponse("/login?erro=1", status_code=303, headers=_SEM_CACHE)

        limite.acertou(ip)
        resposta = RedirectResponse("/", status_code=303, headers=_SEM_CACHE)
        resposta.set_cookie(
            COOKIE,
            sessoes.criar(),
            max_age=8 * 3600,
            path="/",
            secure=cookie_seguro,
            httponly=True,
            samesite="strict",
        )
        return resposta

    @router.post("/logout", include_in_schema=False)
    def sair(request: Request) -> Response:
        if not _origem_permitida(request):
            return PlainTextResponse("Origem não permitida.", status_code=403)
        sessoes.encerrar(request.cookies.get(COOKIE))
        resposta = RedirectResponse("/login", status_code=303, headers=_SEM_CACHE)
        resposta.delete_cookie(
            COOKIE, path="/", secure=cookie_seguro, httponly=True, samesite="strict"
        )
        return resposta

    return router
