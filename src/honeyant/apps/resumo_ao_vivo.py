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

import contextlib
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
LIMITE_BYTES = 1024 * 1024  # um resumo tem poucos KB; mais que isso não é o nosso servidor
# Sem consulta bem-sucedida há mais que isso, o "ao vivo" é velho demais para ser chamado assim
# (thread morto ou consulta travada): o painel volta para o cache/embutido.
AO_VIVO_VALIDO_S = 60


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


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    """O resumo-api nunca redireciona; seguir um redirecionamento reenviaria a chave."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise urllib.error.HTTPError(req.full_url, code, "redirecionamento recusado", headers, fp)


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
            urllib.request.ProxyHandler({}),
            _SemRedirecionar(),
            urllib.request.HTTPSHandler(context=contexto),
        )

    def buscar(self) -> ResumoDeAmeaca:
        pedido = urllib.request.Request(  # noqa: S310  # URL do próprio projeto
            self._url, headers={"Authorization": f"Bearer {self._chave}"}
        )
        try:
            with self._abridor.open(pedido, timeout=self._timeout) as r:
                corpo = r.read(LIMITE_BYTES + 1)
        except urllib.error.HTTPError as erro:
            if erro.code in (401, 403):
                raise ChaveInvalida from None
            if erro.code == 429:
                raise FalhaDeRede("IP bloqueado por 15 min (muitas chaves erradas)") from None
            raise FalhaDeRede(f"HTTP {erro.code}") from None
        except urllib.error.URLError as erro:
            if isinstance(erro.reason, ssl.SSLCertVerificationError):
                detalhe = getattr(erro.reason, "verify_message", "") or ""
                motivo = (
                    f"certificado não confere ({detalhe})" if detalhe else "certificado não confere"
                )
                raise FalhaDeRede(motivo) from None
            raise FalhaDeRede(str(erro.reason)) from None
        except Exception as erro:  # noqa: BLE001  # nada inesperado pode virar 500 na página
            raise FalhaDeRede(type(erro).__name__) from None
        if len(corpo) > LIMITE_BYTES:
            raise RespostaInvalida("resposta grande demais para um resumo")
        try:
            return ResumoDeAmeaca.model_validate_json(corpo)
        except ValidationError:
            raise RespostaInvalida("a resposta não é um ResumoDeAmeaca") from None


class FonteDoResumoAoVivo:
    """Porta `FonteDoResumo` do app.

    Em segundo plano (o app): `iniciar()` sobe **um** thread que consulta a EC2 na abertura e
    depois a cada 15 s, contados do início de cada consulta (com recuo nas falhas, parando no
    401). `resumo()` só lê o estado: responde na hora e já com o último resultado.

    `em_segundo_plano=False` (testes de lógica): `resumo()` consulta quando está na hora.
    `avisar` recebe as mudanças de estado (o app manda para o console); `ao_recusar` é
    chamado uma vez depois de um 401 (o app esquece a chave salva)."""

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
        self._iniciado = False
        self._ultimo_ao_vivo: ResumoComOrigem | None = None
        self._quando_ao_vivo = 0.0  # relógio da última consulta bem-sucedida
        self._estado = ""  # última mensagem mandada ao console
        self.espera_s: float = INTERVALO_S

    def iniciar(self) -> None:
        """Sobe o thread de consulta (uma vez). Sem cliente, não há o que consultar."""
        with self._trava:
            if self._iniciado or self._cliente is None or not self._em_segundo_plano:
                return
            self._iniciado = True
        threading.Thread(target=self._laco, daemon=True, name="resumo-ao-vivo").start()

    def _laco(self, dormir: Callable[[float], None] = time.sleep) -> None:
        """Nunca morre em silêncio: um erro inesperado numa rodada vira espera e nova tentativa."""
        while True:
            try:
                espera = self._rodada()
            except Exception:  # noqa: BLE001  # o thread de consulta não pode morrer
                espera = TETO_S
            with self._trava:
                if self._parado:
                    return
            dormir(espera)

    def _rodada(self) -> float:
        """Uma consulta; devolve quanto dormir até a próxima (contando desde o início)."""
        inicio = self._relogio()
        self._atualizar()
        return max(0.0, self.espera_s - (self._relogio() - inicio))

    def resumo(self) -> ResumoComOrigem:
        if not self._em_segundo_plano:
            with self._trava:
                na_hora = (
                    self._cliente is not None
                    and not self._parado
                    and self._relogio() >= self._proxima
                )
            if na_hora:
                self._atualizar()
        with self._trava:
            velho = self._relogio() - self._quando_ao_vivo > AO_VIVO_VALIDO_S
            if self._parado or self._ultimo_ao_vivo is None or velho:
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
        atual = ResumoComOrigem(origem="ao_vivo", resumo=resumo, atualizado_em=self._agora())
        self._gravar_cache(atual)
        with self._trava:
            self._falhas = 0
            self._agendar(INTERVALO_S)
            self._ultimo_ao_vivo = atual
            self._quando_ao_vivo = self._relogio()
        self._mudar_estado("Ao vivo: os ataques da isca estão chegando.")

    def _mudar_estado(self, mensagem: str) -> None:
        if mensagem != self._estado:
            self._estado = mensagem
            # O aviso no console é só cortesia: nunca pode derrubar o thread de consulta.
            with contextlib.suppress(Exception):
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
            with contextlib.suppress(OSError):  # antivírus segurando o temporário
                Path(temporario).unlink(missing_ok=True)
