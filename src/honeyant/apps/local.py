"""Composition root do notebook: fixtures + pathfinder + painel (spec, seção 4).

Uso:
    uv run honeyant-local            # http://127.0.0.1:8000/
Variáveis: HONEYANT_PERFIL (inseguro|seguro), HONEYANT_DEMO_DIR, HONEYANT_HOST,
HONEYANT_PORTA. Até o painel ter autenticação, o padrão escuta só em 127.0.0.1.
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.core.evidencia import EvidenciaDeRede
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.core.rota import Snapshot
from honeyant.painel.app import Encaixe, criar_app
from honeyant.pathfinder.aco import ACO, ParametrosACO
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.prever import ColetorDeSnapshots, prever_rota

HOSTS_LOCAIS = frozenset({"127.0.0.1", "localhost", "::1"})
# Cabeçalho Host aceito pelo TrustedHost: o Starlette mantém os colchetes do IPv6.
HOSTS_DO_CABECALHO = ("127.0.0.1", "localhost", "[::1]")


@dataclass(frozen=True)
class ConfigLocal:
    perfil: TipoDePerfil
    demo_dir: Path
    host: str
    porta: int

    @classmethod
    def de_ambiente(cls, env: Mapping[str, str]) -> "ConfigLocal":
        host = env.get("HONEYANT_HOST", "127.0.0.1")
        # Painel ainda sem login nem TLS (spec, seção 12): só a própria máquina acessa.
        if host not in HOSTS_LOCAIS:
            raise ValueError(
                f"HONEYANT_HOST={host!r} recusado: até o painel ter autenticação, "
                "use 127.0.0.1 (ou localhost/::1)"
            )
        return cls(
            perfil=TipoDePerfil(env.get("HONEYANT_PERFIL", "inseguro")),
            demo_dir=Path(env.get("HONEYANT_DEMO_DIR", "docs/demo")),
            host=host,
            porta=int(env.get("HONEYANT_PORTA", "8000")),
        )


class FonteDasFixtures:
    """Implementa a porta `FonteDoFormigueiro` do painel rodando o ACO de verdade."""

    def __init__(
        self,
        perfil: PerfilDaCasa,
        evidencias: Sequence[EvidenciaDeRede],
        resumo: ResumoDeAmeaca,
    ) -> None:
        self._perfil = perfil
        self._evidencias = list(evidencias)
        self._resumo = resumo
        self._modelo = ModeloDeRisco()

    def snapshots(self, semente: int) -> list[Snapshot]:
        coletor = ColetorDeSnapshots()
        aco = ACO(ParametrosACO(semente=semente), observadores=[coletor])
        prever_rota(self._perfil, self._evidencias, self._resumo, aco, self._modelo)
        return coletor.snapshots


def _ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def montar(
    config: ConfigLocal,
    intervalo_base: float = 0.6,
    intervalo_minimo: float = 0.15,
    encaixe: Encaixe = Encaixe(),  # noqa: B008 (dataclass congelada, imutável)
) -> FastAPI:
    """Monta o painel. O login (PR do Gustavo) chega pelo `encaixe` (spec, seção 3.5)."""
    tipo = config.perfil.value
    perfil = PerfilDaCasa.model_validate(_ler_json(config.demo_dir / f"perfil-{tipo}.json"))
    evidencias = [
        EvidenciaDeRede.model_validate(e)
        for e in _ler_json(config.demo_dir / f"evidencias-{tipo}.json")
    ]
    resumo = ResumoDeAmeaca.model_validate(_ler_json(config.demo_dir / "resumo-congelado.json"))
    fonte = FonteDasFixtures(perfil, evidencias, resumo)
    return criar_app(
        perfil,
        fonte,
        intervalo_base=intervalo_base,
        intervalo_minimo=intervalo_minimo,
        encaixe=encaixe,
        hosts_permitidos=HOSTS_DO_CABECALHO,
    )


def main() -> None:
    import uvicorn  # só o modo local precisa do servidor web

    config = ConfigLocal.de_ambiente(os.environ)
    uvicorn.run(montar(config), host=config.host, port=config.porta)


if __name__ == "__main__":
    main()
