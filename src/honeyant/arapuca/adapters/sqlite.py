"""Repositório SQLite (modo WAL). A isca é a única escritora."""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from honeyant.arapuca.ports import RETENCAO, TETO_BYTES, TETO_EVENTOS
from honeyant.core.eventos import EventoDeAtaque, Servico

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    servico TEXT NOT NULL,
    dados TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eventos_ts ON eventos (ts);
CREATE TABLE IF NOT EXISTS acumulado (
    servico TEXT PRIMARY KEY,
    total INTEGER NOT NULL
);
"""

_LOTE = 1000


class RepositorioSqlite:
    def __init__(
        self,
        caminho: Path,
        teto_eventos: int = TETO_EVENTOS,
        teto_bytes: int = TETO_BYTES,
    ) -> None:
        self._teto_eventos = teto_eventos
        self._teto_bytes = teto_bytes
        self._trava = threading.Lock()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: o servidor grava via asyncio.to_thread; a trava serializa.
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.executescript(_ESQUEMA)

    def salvar(self, evento: EventoDeAtaque) -> None:
        with self._trava, self._con:
            self._con.execute(
                "INSERT INTO eventos (id, ts, servico, dados) VALUES (?, ?, ?, ?)",
                (
                    str(evento.id),
                    evento.ts.isoformat(),
                    evento.servico.value,
                    evento.model_dump_json(),
                ),
            )
            self._con.execute(
                "INSERT INTO acumulado (servico, total) VALUES (?, 1) "
                "ON CONFLICT (servico) DO UPDATE SET total = total + 1",
                (evento.servico.value,),
            )

    def contar(self) -> int:
        with self._trava:
            return self._con.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]

    def acumulado_por_servico(self) -> dict[Servico, int]:
        with self._trava:
            linhas = self._con.execute("SELECT servico, total FROM acumulado").fetchall()
        return {Servico(s): t for s, t in linhas}

    def aplicar_limites(self, agora: datetime) -> int:
        limite = (agora - RETENCAO).isoformat()
        with self._trava, self._con:
            removidos = self._con.execute("DELETE FROM eventos WHERE ts < ?", (limite,)).rowcount
            total = self._con.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]
            excesso = total - self._teto_eventos
            if excesso > 0:
                removidos += self._remover_mais_antigos(excesso)
            while self._tamanho_bytes() > self._teto_bytes and self._ha_eventos():
                removidos += self._remover_mais_antigos(_LOTE)
        return removidos

    def modo_journal(self) -> str:
        with self._trava:
            return self._con.execute("PRAGMA journal_mode").fetchone()[0]

    def _remover_mais_antigos(self, quantidade: int) -> int:
        return self._con.execute(
            "DELETE FROM eventos WHERE id IN (SELECT id FROM eventos ORDER BY ts LIMIT ?)",
            (quantidade,),
        ).rowcount

    def _tamanho_bytes(self) -> int:
        paginas = self._con.execute("PRAGMA page_count").fetchone()[0]
        livres = self._con.execute("PRAGMA freelist_count").fetchone()[0]
        tamanho = self._con.execute("PRAGMA page_size").fetchone()[0]
        return (paginas - livres) * tamanho

    def _ha_eventos(self) -> bool:
        return self._con.execute("SELECT 1 FROM eventos LIMIT 1").fetchone() is not None
