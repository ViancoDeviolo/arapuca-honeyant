"""Composition root do notebook: fixtures + pathfinder + painel (spec, seção 4).

Uso:
    uv run honeyant-local            # http://127.0.0.1:8000/
Variáveis: HONEYANT_DEMO_DIR, HONEYANT_HOST, HONEYANT_PORTA. O perfil (inseguro|seguro)
vem da query de cada requisição. Até o painel ter autenticação, só escuta em 127.0.0.1.
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
from honeyant.painel.modelos import AnaliseDeRota, ResumoComOrigem
from honeyant.pathfinder.aco import ACO, ParametrosACO
from honeyant.pathfinder.fuzzy import ModeloDeRisco
from honeyant.pathfinder.ports import ObservadorDeIteracao
from honeyant.pathfinder.prever import ColetorDeSnapshots, analisar_rota, prever_rota

HOSTS_LOCAIS = frozenset({"127.0.0.1", "localhost", "::1"})
# Cabeçalho Host aceito pelo TrustedHost: o Starlette mantém os colchetes do IPv6.
HOSTS_DO_CABECALHO = ("127.0.0.1", "localhost", "[::1]")


@dataclass(frozen=True)
class ConfigLocal:
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
            demo_dir=Path(env.get("HONEYANT_DEMO_DIR", "docs/demo")),
            host=host,
            porta=int(env.get("HONEYANT_PORTA", "8000")),
        )


def _ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


class FonteDasFixtures:
    """Implementa a porta `FonteDoFormigueiro` do painel com o pathfinder de verdade."""

    def __init__(
        self,
        casas: Mapping[TipoDePerfil, PerfilDaCasa],
        evidencias_por_perfil: Mapping[TipoDePerfil, Sequence[EvidenciaDeRede]],
        resumo: ResumoDeAmeaca,
        demo_dir: Path,
    ) -> None:
        self._casas = dict(casas)
        self._evidencias = {t: list(e) for t, e in evidencias_por_perfil.items()}
        self._resumo = resumo
        self._demo_dir = demo_dir
        self._modelo = ModeloDeRisco()

    @property
    def casas(self) -> dict[TipoDePerfil, PerfilDaCasa]:
        return dict(self._casas)

    def executar(
        self, perfil: TipoDePerfil, semente: int, observadores: Sequence[ObservadorDeIteracao]
    ) -> None:
        """Roda o ACO no perfil, avisando cada observador a cada iteração."""
        aco = ACO(ParametrosACO(semente=semente), observadores=list(observadores))
        prever_rota(self._casas[perfil], self._evidencias[perfil], self._resumo, aco, self._modelo)

    def snapshots(self, perfil: TipoDePerfil, semente: int) -> list[Snapshot]:
        coletor = ColetorDeSnapshots()
        self.executar(perfil, semente, [coletor])
        return coletor.snapshots

    def replay(self, perfil: TipoDePerfil) -> list[Snapshot] | None:
        arquivo = self._demo_dir / f"replay-{perfil.value}.jsonl"
        if not arquivo.is_file():
            return None
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
        return [Snapshot.model_validate_json(linha) for linha in linhas if linha.strip()]

    def analise(self, perfil: TipoDePerfil) -> AnaliseDeRota:
        a = analisar_rota(self._casas[perfil], self._evidencias[perfil], self._resumo, self._modelo)
        nos_da_rota = a.rota.nos if a.rota else []
        da_rota = {f"{o}->{d}" for o, d in zip(nos_da_rota, nos_da_rota[1:], strict=False)}
        por_no: dict[str, float] = {n.id: 0.0 for n in self._casas[perfil].nos}
        for chave, risco in a.riscos.items():
            for no in chave.split("->"):
                por_no[no] = max(por_no[no], risco)
        return AnaliseDeRota(
            rota=a.rota,
            riscos={c: r for c, r in a.riscos.items() if c in da_rota},
            riscos_por_no=por_no,
            bloqueadas=a.bloqueadas,
        )


class FonteDoResumoLocal:
    """O `resumo-real-*.json` mais recente (pelo nome); senão, o resumo de exemplo."""

    def __init__(self, demo_dir: Path) -> None:
        self._demo_dir = demo_dir

    def resumo(self) -> ResumoComOrigem:
        reais = sorted(self._demo_dir.glob("resumo-real-*.json"))
        if reais:
            return ResumoComOrigem(
                origem="real", resumo=ResumoDeAmeaca.model_validate(_ler_json(reais[-1]))
            )
        exemplo = _ler_json(self._demo_dir / "resumo-congelado.json")
        return ResumoComOrigem(origem="exemplo", resumo=ResumoDeAmeaca.model_validate(exemplo))


def carregar_fontes(demo_dir: Path) -> tuple[FonteDasFixtures, FonteDoResumoLocal]:
    """Lê perfis, evidências e resumo de `demo_dir` (o painel e o gravador de replay)."""
    casas = {
        t: PerfilDaCasa.model_validate(_ler_json(demo_dir / f"perfil-{t.value}.json"))
        for t in TipoDePerfil
    }
    evidencias = {
        t: [
            EvidenciaDeRede.model_validate(e)
            for e in _ler_json(demo_dir / f"evidencias-{t.value}.json")
        ]
        for t in TipoDePerfil
    }
    fonte_resumo = FonteDoResumoLocal(demo_dir)
    # As rotas usam o mesmo resumo que o cartão mostra (spec do painel, 3.7).
    fonte = FonteDasFixtures(casas, evidencias, fonte_resumo.resumo().resumo, demo_dir)
    return fonte, fonte_resumo


def montar(
    config: ConfigLocal,
    intervalo_base: float = 0.6,
    intervalo_minimo: float = 0.15,
    encaixe: Encaixe = Encaixe(),  # noqa: B008 (dataclass congelada, imutável)
) -> FastAPI:
    """Monta o painel. O login (PR do Gustavo) chega pelo `encaixe` (spec, seção 3.5)."""
    fonte, fonte_resumo = carregar_fontes(config.demo_dir)
    return criar_app(
        fonte.casas,
        fonte,
        fonte_resumo,
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
