"""Chave de acesso do resumo-api (spec do aplicativo ao vivo, seção 3.1).

- A EC2 guarda só o **hash scrypt** da chave, no mesmo formato do login do painel
  (`scrypt$N$r$p$sal$hash`). O intel não importa o painel (regra de dependência), então o
  hash é feito aqui, com os mesmos parâmetros.
- A chave recebida passa pelo mesmo scrypt e é comparada com `hmac.compare_digest`, em
  tempo constante.
- **5 erros por IP em 15 min bloqueiam aquele IP por 15 min.** Durante o bloqueio a chave
  nem é verificada. Os números são os do login do painel.
- A chave nunca é registrada nem devolvida.
"""

import base64
import binascii
import hashlib
import hmac
import os
import threading
import time
from collections.abc import Callable
from typing import Literal

_N, _R, _P, _DKLEN, _TAMANHO_SAL = 16384, 8, 1, 32, 16
LIMITE_ERROS = 5
JANELA_S = 15 * 60
BLOQUEIO_S = 15 * 60
# Cada scrypt usa ~16 MiB; o resumo-api tem 128 MiB. No máximo 2 ao mesmo tempo.
SCRYPT_SIMULTANEOS = 2

Resultado = Literal["ok", "negado", "bloqueado"]


def _scrypt(chave: str, sal: bytes, n: int, r: int, p: int, tamanho: int) -> bytes:
    return hashlib.scrypt(chave.encode("utf-8"), salt=sal, n=n, r=r, p=p, dklen=tamanho)


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(chave: str, *, sal: bytes | None = None) -> str:
    sal = sal if sal is not None else os.urandom(_TAMANHO_SAL)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(_scrypt(chave, sal, _N, _R, _P, _DKLEN))}"


def _decompor(salvo: str) -> tuple[int, int, int, bytes, bytes] | None:
    partes = salvo.split("$")
    if len(partes) != 6 or partes[0] != "scrypt":
        return None
    try:
        n, r, p = int(partes[1]), int(partes[2]), int(partes[3])
        sal = base64.b64decode(partes[4], validate=True)
        esperado = base64.b64decode(partes[5], validate=True)
    except (ValueError, binascii.Error):
        return None
    if n < 2 or r < 1 or p < 1 or not sal or not esperado:
        return None
    return n, r, p, sal, esperado


def hash_valido(salvo: str) -> bool:
    return _decompor(salvo) is not None


def _chave_do_cabecalho(cabecalho: str | None) -> str | None:
    if not cabecalho or not cabecalho.startswith("Bearer "):
        return None
    chave = cabecalho[len("Bearer ") :].strip()
    return chave or None


class ControleDeAcesso:
    def __init__(
        self,
        hash_salvo: str,
        limite: int = LIMITE_ERROS,
        janela_s: float = JANELA_S,
        bloqueio_s: float = BLOQUEIO_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        partes = _decompor(hash_salvo.strip())
        if partes is None:
            # Nunca repete o valor: ele é segredo.
            raise ValueError("hash da chave inválido (gere com `uv run honeyant-chave-app`)")
        self._n, self._r, self._p, self._sal, self._esperado = partes
        self._limite, self._janela, self._bloqueio = limite, janela_s, bloqueio_s
        self._relogio = relogio
        self._erros: dict[str, list[float]] = {}
        self._bloqueado_ate: dict[str, float] = {}
        # O servidor atende cada conexão num thread: o estado do bloqueio fica sob trava.
        self._trava = threading.Lock()
        self._scrypts = threading.BoundedSemaphore(SCRYPT_SIMULTANEOS)

    def verificar(self, ip: str, cabecalho_authorization: str | None) -> Resultado:
        with self._trava:
            agora = self._relogio()
            ate = self._bloqueado_ate.get(ip)
            if ate is not None:
                if agora < ate:
                    return "bloqueado"
                del self._bloqueado_ate[ip]
        chave = _chave_do_cabecalho(cabecalho_authorization)
        if chave is not None:
            with self._scrypts:  # fora da trava: o scrypt é lento
                calculado = _scrypt(
                    chave, self._sal, self._n, self._r, self._p, len(self._esperado)
                )
            if hmac.compare_digest(calculado, self._esperado):
                with self._trava:
                    if self._bloqueado_ate.get(ip, 0) > agora:
                        return "bloqueado"  # o IP foi bloqueado enquanto esta conferia
                    self._erros.pop(ip, None)
                return "ok"
        with self._trava:
            if self._bloqueado_ate.get(ip, 0) > agora:
                return "bloqueado"
            recentes = [t for t in self._erros.get(ip, []) if agora - t < self._janela]
            recentes.append(agora)
            if len(recentes) >= self._limite:
                self._bloqueado_ate[ip] = agora + self._bloqueio
                self._erros.pop(ip, None)
            else:
                self._erros[ip] = recentes
        return "negado"
