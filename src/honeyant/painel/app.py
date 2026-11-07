"""App web do painel: casa, resumo, rotas e formigueiro por SSE (spec, seções 3 e 11).

O login não mora aqui: chega pelo `Encaixe` (spec, seção 3.5). Sem encaixe, nenhuma rota
é protegida, e por isso o composition root só sobe o painel em 127.0.0.1.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response, params
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.core.rota import Snapshot
from honeyant.painel.modelos import AnaliseDeRota, ResumoComOrigem
from honeyant.painel.ports import FonteDoFormigueiro, FonteDoResumo
from honeyant.painel.streams import RegistroDeStreams

ESTATICOS = Path(__file__).parent / "static"
CSP = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)
HOSTS_PADRAO = ("127.0.0.1", "localhost")

Dormir = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class Encaixe:
    """O que o login injeta no painel (spec, seção 3.5).

    - `protecao_api`: dependências de `/api/v1/*` (respondem 401 sem sessão).
    - `protecao_pagina`: dependências de `/` (redirecionam para `/login` sem sessão).
    - `routers`: rotas do próprio login, registradas antes e sem proteção.

    `/static/*` fica fora de propósito: `StaticFiles` não aceita dependências, e os
    estáticos são o mesmo código público do repositório, sem dado nenhum. Os dados só
    saem pela API, que é protegida.
    """

    protecao_api: Sequence[params.Depends] = ()
    protecao_pagina: Sequence[params.Depends] = ()
    routers: Sequence[APIRouter] = ()


def _evento(nome: str, dados: str) -> str:
    return f"event: {nome}\ndata: {dados}\n\n"


def criar_app(
    casas: Mapping[TipoDePerfil, PerfilDaCasa],
    fonte: FonteDoFormigueiro,
    fonte_resumo: FonteDoResumo,
    intervalo_base: float = 0.6,
    intervalo_minimo: float = 0.15,
    dormir: Dormir = asyncio.sleep,
    *,
    encaixe: Encaixe = Encaixe(),  # noqa: B008 (dataclass congelada, imutável)
    hosts_permitidos: Sequence[str] = HOSTS_PADRAO,
    registro: RegistroDeStreams | None = None,
) -> FastAPI:
    streams = registro or RegistroDeStreams()
    app = FastAPI(title="HoneyAnt", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, chamar_proximo) -> Response:
        resposta = await chamar_proximo(request)
        resposta.headers["Content-Security-Policy"] = CSP
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        return resposta

    # Adicionado por último, roda primeiro: Host estranho (DNS rebinding) recebe 400.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(hosts_permitidos))

    api = APIRouter(prefix="/api/v1", dependencies=list(encaixe.protecao_api))
    pagina = APIRouter(dependencies=list(encaixe.protecao_pagina))

    @api.get("/casa")
    def ver_casa(perfil: TipoDePerfil = TipoDePerfil.INSEGURO) -> dict:
        return casas[perfil].model_dump(mode="json")

    @api.get("/resumo")
    def ver_resumo() -> ResumoComOrigem:
        return fonte_resumo.resumo()

    @api.get("/rotas")
    def ver_rotas() -> dict[TipoDePerfil, AnaliseDeRota]:
        return {t: fonte.analise(t) for t in TipoDePerfil}

    @api.get("/replay")
    def ver_replay() -> dict[TipoDePerfil, bool]:
        return {t: fonte.replay(t) is not None for t in TipoDePerfil}

    tem_login = bool(encaixe.routers)

    @api.get("/sessao")
    def ver_sessao() -> dict[str, bool]:
        """Diz à página se há login, para ela mostrar o botão Sair (só chega aqui logado)."""
        return {"login": tem_login}

    @api.get("/formigueiro/stream")
    async def formigueiro(
        request: Request,
        perfil: TipoDePerfil = TipoDePerfil.INSEGURO,
        modo: Literal["prever", "replay"] = "prever",
        semente: int = Query(42, ge=0, le=2**31 - 1),
        velocidade: float = Query(1.0, ge=0.25, le=4, allow_inf_nan=False),
    ) -> StreamingResponse:
        gravados: list[Snapshot] | None = None
        if modo == "replay":
            replay = fonte.replay(perfil)
            if replay is None:
                raise HTTPException(404, "replay indisponível para este perfil")
            gravados = list(replay)
        # No máximo um snapshot a cada `intervalo_minimo` (spec: 150 ms).
        espera = max(intervalo_minimo, intervalo_base / velocidade)
        cliente = request.client.host if request.client else "?"

        async def gerar() -> AsyncIterator[str]:
            parar = streams.abrir(cliente)
            try:
                if gravados is None:
                    # O ACO é CPU puro: roda fora do loop para não travar outras conexões.
                    snapshots = await asyncio.to_thread(fonte.snapshots, perfil, semente)
                else:
                    snapshots = gravados
                for i, s in enumerate(snapshots):
                    if i:
                        await dormir(espera)
                    if parar.is_set():  # o mesmo cliente abriu um stream mais novo
                        break
                    yield _evento("snapshot", s.model_dump_json())
                yield _evento("fim", "{}")
            finally:
                streams.fechar(cliente, parar)

        return StreamingResponse(
            gerar(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @pagina.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        return FileResponse(ESTATICOS / "index.html")

    for router in encaixe.routers:
        app.include_router(router)
    app.include_router(api)
    app.include_router(pagina)
    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
    return app
