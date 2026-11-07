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
        # ProxyHandler({}): sempre direto. Pelo proxy do sistema, a EC2 veria o IP do proxy,
        # não o da rede liberada no Security Group.
        self._abridor = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=contexto)
        )

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
            if erro.code == 429:
                raise FalhaDeRede("IP bloqueado por 15 min (muitas chaves erradas)") from None
            raise FalhaDeRede(f"HTTP {erro.code}") from None
        except urllib.error.URLError as erro:
            if isinstance(erro.reason, ssl.SSLCertVerificationError):
                raise FalhaDeRede("certificado não confere") from None
            raise FalhaDeRede(str(erro.reason)) from None
        except Exception as erro:  # noqa: BLE001  # nada inesperado pode virar 500 na página
            raise FalhaDeRede(type(erro).__name__) from None
        try:
            return ResumoDeAmeaca.model_validate_json(corpo)
        except ValidationError:
            raise RespostaInvalida("a resposta não é um ResumoDeAmeaca") from None


class FonteDoResumoAoVivo:
    """Porta `FonteDoResumo` do app. `resumo()` responde **na hora** com o nível disponível;
    a consulta à EC2 roda num thread em segundo plano (`em_segundo_plano=False` só nos testes
    de lógica). `avisar` recebe as mudanças de estado (o app manda para o console);
    `ao_recusar` é chamado uma vez depois de um 401 (o app esquece a chave salva)."""

    def __init__(
        self,
        cliente: ClienteResumo | None,
        cache: Path,
        embutido: FonteDoResumo,
        relogio: Callable[[], float] = time.monotonic,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
        em_segundo_plano: bool = True,
        avisar: Callable[[str], None] = lambda _mensagem: None,
        ao_recusar: Callable[[], None] | None = None,
    ) -> None:
        self._cliente = cliente
        self._cache = cache
        self._embutido = embutido
        self._relogio = relogio
        self._agora = agora
        self._em_segundo_plano = em_segundo_plano
        self._avisar = avisar
        self._ao_recusar = ao_recusar
        self._trava = threading.Lock()
        self._proxima = 0.0  # instante (relógio) da próxima consulta permitida
        self._falhas = 0
        self._parado = False  # depois de um 401
        self._em_andamento = False
        self._ultimo_ao_vivo: ResumoComOrigem | None = None
        self._estado = ""  # última mensagem mandada ao console
        self.espera_s: float = INTERVALO_S

    def resumo(self) -> ResumoComOrigem:
        with self._trava:
            consultar = (
                self._cliente is not None
                and not self._parado
                and not self._em_andamento
                and self._relogio() >= self._proxima
            )
            if consultar:
                self._em_andamento = True
        if consultar:
            if self._em_segundo_plano:
                threading.Thread(target=self._atualizar, daemon=True).start()
            else:
                self._atualizar()
        with self._trava:
            if self._parado or self._ultimo_ao_vivo is None:
                return self._reserva()
            return self._ultimo_ao_vivo

    def _atualizar(self) -> None:
        try:
            resumo = self._cliente.buscar()
        except ChaveInvalida:
            with self._trava:
                self._parado = True
            if self._ao_recusar is not None:
                self._ao_recusar()
            self._mudar_estado(
                "Chave de acesso inválida: o app parou de consultar a isca. "
                "Feche, abra de novo e cole a chave certa."
            )
            return
        except Exception as erro:  # noqa: BLE001  # FalhaDeRede, RespostaInvalida e o resto
            with self._trava:
                self._falhas += 1
                self._agendar(min(INTERVALO_S * 2 ** (self._falhas - 1), TETO_S))
                self._ultimo_ao_vivo = None
            self._mudar_estado(
                f"Offline ({erro or type(erro).__name__}): usando o resumo guardado."
            )
            return
        finally:
            with self._trava:
                self._em_andamento = False
        atual = ResumoComOrigem(origem="ao_vivo", resumo=resumo, atualizado_em=self._agora())
        self._gravar_cache(atual)
        with self._trava:
            self._falhas = 0
            self._agendar(INTERVALO_S)
            self._ultimo_ao_vivo = atual
        self._mudar_estado("Ao vivo: os ataques da isca estão chegando.")

    def _mudar_estado(self, mensagem: str) -> None:
        if mensagem != self._estado:
            self._estado = mensagem
            self._avisar(mensagem)

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
