"""Resumo ao vivo no app: cliente HTTPS do resumo-api (spec do aplicativo ao vivo, 3.3).

A conexão só confia na CA do projeto, confere o IP do servidor no certificado e exige
TLS 1.2 ou superior.

A `FonteDoResumoAoVivo` implementa a porta `FonteDoResumo` do painel em três níveis:

1. **ao vivo** — consulta o resumo-api (timeout de 5 s, no máximo a cada 15 s);
2. **cache** — o último resumo ao vivo, em `%APPDATA%\\HoneyAnt\\ultimo-resumo.json`
   (origem `offline`);
3. **embutido** — o resumo que veio no `.exe`.

Erro de rede: recuo exponencial (15, 30, 60… até 300 s), que volta a 15 s no primeiro
sucesso. **401: o app para de consultar** até ser reaberto e mostra "chave de acesso
inválida" — assim nunca chega aos 5 erros que bloqueiam o IP.
"""

import json
import os
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.painel.modelos import ResumoComOrigem
from honeyant.painel.ports import FonteDoResumo

INTERVALO_S = 15
TETO_S = 300
AVISO_CHAVE_INVALIDA = "chave de acesso inválida"


class ChaveInvalida(Exception):
    pass


class FalhaDeRede(Exception):
    pass


class RespostaInvalida(Exception):
    pass


def contexto_cliente(ca: Path) -> ssl.SSLContext:
    """Só a CA do projeto; nome (IP) conferido no SAN; TLS 1.2+."""
    contexto = ssl.create_default_context(cafile=str(ca))
    contexto.check_hostname = True
    contexto.verify_mode = ssl.CERT_REQUIRED
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    return contexto


class ClienteResumo:
    def __init__(
        self, url: str, chave: str, contexto: ssl.SSLContext, timeout_s: float = 5
    ) -> None:
        self._url = f"{url.rstrip('/')}/api/v1/resumo"
        self._chave = chave
        self._timeout = timeout_s
        self._abridor = urllib.request.build_opener(urllib.request.HTTPSHandler(context=contexto))

    def buscar(self) -> ResumoDeAmeaca:
        pedido = urllib.request.Request(  # noqa: S310  # URL do próprio projeto
            self._url, headers={"Authorization": f"Bearer {self._chave}"}
        )
        try:
            with self._abridor.open(pedido, timeout=self._timeout) as r:
                corpo = r.read()
        except urllib.error.HTTPError as erro:
            if erro.code in (401, 403):
                raise ChaveInvalida from None
            raise FalhaDeRede(f"HTTP {erro.code}") from None
        except (urllib.error.URLError, OSError, ssl.SSLError) as erro:
            raise FalhaDeRede(str(getattr(erro, "reason", erro))) from None
        try:
            return ResumoDeAmeaca.model_validate_json(corpo)
        except ValidationError:
            raise RespostaInvalida("a resposta não é um ResumoDeAmeaca") from None


class FonteDoResumoAoVivo:
    def __init__(
        self,
        cliente: ClienteResumo | None,
        cache: Path,
        embutido: FonteDoResumo,
        relogio: Callable[[], float] = time.monotonic,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._cliente = cliente
        self._cache = cache
        self._embutido = embutido
        self._relogio = relogio
        self._agora = agora
        self._trava = threading.Lock()
        self._proxima = 0.0  # instante (relógio) da próxima consulta permitida
        self._falhas = 0
        self._parado = False  # depois de um 401
        self._ultimo_ao_vivo: ResumoComOrigem | None = None
        self.espera_s: float = INTERVALO_S

    def resumo(self) -> ResumoComOrigem:
        with self._trava:
            if self._cliente is None or self._parado:
                return self._reserva()
            if self._relogio() < self._proxima:
                return self._ultimo_ao_vivo or self._reserva()
            try:
                resumo = self._cliente.buscar()
            except ChaveInvalida:
                self._parado = True
                return self._reserva()
            except (FalhaDeRede, RespostaInvalida):
                self._falhas += 1
                self._agendar(min(INTERVALO_S * 2 ** (self._falhas - 1), TETO_S))
                self._ultimo_ao_vivo = None
                return self._reserva()
            self._falhas = 0
            self._agendar(INTERVALO_S)
            atual = ResumoComOrigem(origem="ao_vivo", resumo=resumo, atualizado_em=self._agora())
            self._gravar_cache(atual)
            self._ultimo_ao_vivo = atual
            return atual

    def _agendar(self, espera: float) -> None:
        self.espera_s = espera
        self._proxima = self._relogio() + espera

    def _reserva(self) -> ResumoComOrigem:
        aviso = AVISO_CHAVE_INVALIDA if self._parado else None
        do_cache = self._ler_cache()
        if do_cache is not None:
            return do_cache.model_copy(update={"origem": "offline", "aviso": aviso})
        return self._embutido.resumo().model_copy(update={"aviso": aviso})

    def _ler_cache(self) -> ResumoComOrigem | None:
        try:
            dados = json.loads(self._cache.read_text(encoding="utf-8"))
            return ResumoComOrigem(
                origem="offline",
                resumo=ResumoDeAmeaca.model_validate(dados["resumo"]),
                atualizado_em=datetime.fromisoformat(dados["atualizado_em"]),
            )
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            return None  # sem cache, ou cache corrompido: cai no embutido

    def _gravar_cache(self, atual: ResumoComOrigem) -> None:
        conteudo = json.dumps(
            {
                "atualizado_em": atual.atualizado_em.isoformat(),
                "resumo": atual.resumo.model_dump(mode="json"),
            }
        )
        try:
            self._cache.parent.mkdir(parents=True, exist_ok=True)
            fd, temporario = tempfile.mkstemp(dir=self._cache.parent, suffix=".tmp")
        except OSError:
            return  # sem onde gravar: o app segue sem cache
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
                arquivo.write(conteudo)
            os.replace(temporario, self._cache)  # atômico: nunca fica pela metade
        except OSError:
            Path(temporario).unlink(missing_ok=True)
