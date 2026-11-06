"""Adaptador: grava uma execução do ACO em JSON (plano B: replay offline).

Implementa a porta `ObservadorDeIteracao`: o ACO chama `ao_iterar` a cada
iteração sem saber que existe um gravador. O JSON é determinístico (chaves
ordenadas, sem espaços, floats já arredondados no snapshot), então a mesma
semente gera o mesmo arquivo, byte a byte. O painel poderá reproduzir esse
arquivo no formigueiro sem rodar o ACO de novo.

PROVISÓRIO: o formato segue o snapshot local; muda junto com o contrato do
`core` quando ele for combinado com o Gustavo.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from honeyant.pathfinder.dominio.aco import ParametrosACO, ResultadoACO
from honeyant.pathfinder.dominio.snapshot import Snapshot

VERSAO_DO_FORMATO = 1


class GravadorJson:
    """Guarda os snapshots recebidos e os transforma em JSON."""

    def __init__(self) -> None:
        self._snapshots: list[Snapshot] = []

    def ao_iterar(self, snapshot: Snapshot) -> None:
        self._snapshots.append(snapshot)

    def serializar(
        self, semente: int, params: ParametrosACO, resultado: ResultadoACO
    ) -> str:
        """JSON determinístico da execução (parâmetros, resultado e snapshots)."""
        documento = {
            "versao": VERSAO_DO_FORMATO,
            "semente": semente,
            "parametros": asdict(params),
            "resultado": asdict(resultado),
            "snapshots": [asdict(s) for s in self._snapshots],
        }
        return (
            json.dumps(
                documento, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
            + "\n"
        )

    def salvar(
        self,
        caminho: Path,
        semente: int,
        params: ParametrosACO,
        resultado: ResultadoACO,
    ) -> None:
        """Grava o JSON em disco; o caminho vem de quem chama, não de dados externos."""
        texto = self.serializar(semente, params, resultado)
        caminho.write_bytes(texto.encode("utf-8"))
