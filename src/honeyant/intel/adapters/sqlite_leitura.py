"""Leitura do banco da isca em modo somente leitura (`mode=ro`).

A isca é a única escritora (spec, seção 3). Na EC2, o intel e o painel leem o mesmo
arquivo a partir de outro container, com outro usuário, por este leitor. O esquema das
tabelas é o da isca (`arapuca/adapters/sqlite.py`); ele é repetido aqui como texto SQL
porque um módulo não importa outro.
"""

import sqlite3
from pathlib import Path

from honeyant.core.eventos import Servico


class LeitorSqlite:
    def __init__(self, caminho: Path) -> None:
        # Sem esta checagem, um caminho errado viraria um banco vazio novo e o painel
        # mostraria "zero ataques" em vez de um erro.
        if not caminho.is_file():
            raise FileNotFoundError(f"banco da isca não encontrado: {caminho}")
        uri = caminho.resolve().as_uri() + "?mode=ro"
        # check_same_thread=False: o painel lê de threads do servidor web; só há leitura.
        self._con = sqlite3.connect(uri, uri=True, check_same_thread=False)

    def modo(self) -> str:
        return "ro"

    def contar(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]

    def acumulado_por_servico(self) -> dict[Servico, int]:
        linhas = self._con.execute("SELECT servico, total FROM acumulado").fetchall()
        return {Servico(s): t for s, t in linhas}

    def escrita_bloqueada(self) -> bool:
        """Prova, tentando, que esta conexão não consegue alterar o banco."""
        try:
            self._con.execute("CREATE TABLE _sonda (x)")
        except sqlite3.OperationalError as erro:
            if "readonly" in str(erro):
                return True
            raise
        self._con.rollback()
        return False

    def fechar(self) -> None:
        self._con.close()
