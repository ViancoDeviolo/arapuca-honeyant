"""App web mínima do painel: perfil da casa e formigueiro por SSE (spec, seção 11).

Ainda sem autenticação nem TLS (vêm no plano do painel). Por isso o composition root
só a sobe em 127.0.0.1.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from honeyant.core.casa import PerfilDaCasa
from honeyant.painel.ports import FonteDoFormigueiro

ESTATICOS = Path(__file__).parent / "static"
CSP = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)

Dormir = Callable[[float], Awaitable[None]]


def _evento(nome: str, dados: str) -> str:
    return f"event: {nome}\ndata: {dados}\n\n"


def criar_app(
    perfil: PerfilDaCasa,
    fonte: FonteDoFormigueiro,
    intervalo_base: float = 0.6,
    intervalo_minimo: float = 0.15,
    dormir: Dormir = asyncio.sleep,
) -> FastAPI:
    app = FastAPI(title="HoneyAnt", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, chamar_proximo) -> Response:
        resposta = await chamar_proximo(request)
        resposta.headers["Content-Security-Policy"] = CSP
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        return resposta

    @app.get("/api/v1/perfil")
    def ver_perfil() -> dict:
        return perfil.model_dump(mode="json")

    @app.get("/api/v1/formigueiro/stream")
    async def formigueiro(
        modo: Literal["prever"] = "prever",
        semente: int = Query(42, ge=0, le=2**31 - 1),
        velocidade: float = Query(1.0, ge=0.25, le=4),
    ) -> StreamingResponse:
        # No máximo um snapshot a cada `intervalo_minimo` (spec: 150 ms).
        espera = max(intervalo_minimo, intervalo_base / velocidade)

        async def gerar() -> AsyncIterator[str]:
            # O ACO é CPU puro: roda fora do loop para não travar outras conexões.
            snapshots = await asyncio.to_thread(fonte.snapshots, semente)
            for i, s in enumerate(snapshots):
                if i:
                    await dormir(espera)
                yield _evento("snapshot", s.model_dump_json())
            yield _evento("fim", "{}")

        return StreamingResponse(
            gerar(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        return FileResponse(ESTATICOS / "index.html")

    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
    return app
