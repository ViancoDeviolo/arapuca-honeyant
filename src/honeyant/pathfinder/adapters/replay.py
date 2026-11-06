"""Gravador de replay: guarda os snapshots de uma execução do ACO num arquivo .jsonl.

É um Observer (`ObservadorDeIteracao`): o ACO avisa a cada iteração sem saber que
está sendo gravado. O arquivo gerado é o plano B offline da demonstração: o painel
reproduz o formigueiro a partir dele, sem rodar o ACO nem depender de rede.

Formato: uma linha por iteração, cada linha é um `Snapshot` serializado pelo próprio
contrato do `core`. Mesma semente → mesmo arquivo, byte a byte.
"""

import os
import tempfile
from pathlib import Path

from honeyant.core.rota import Snapshot


class GravadorDeReplay:
    """Acumula os snapshots em memória e grava tudo de uma vez em `salvar`.

    Gravar só no fim evita um arquivo pela metade se a execução for interrompida.
    O tamanho é limitado pelo próprio ACO (no máximo 1.000 iterações).
    """

    def __init__(self) -> None:
        self._linhas: list[str] = []

    def notificar(self, snapshot: Snapshot) -> None:
        self._linhas.append(snapshot.model_dump_json())

    @property
    def total(self) -> int:
        return len(self._linhas)

    def serializar(self) -> str:
        """Conteúdo do .jsonl: uma linha por snapshot, terminando em quebra de linha."""
        return "".join(f"{linha}\n" for linha in self._linhas)

    def salvar(self, destino: Path | str) -> Path:
        """Grava de forma atômica: escreve num temporário e troca pelo destino.

        Assim quem estiver lendo o replay (o painel) nunca vê um arquivo incompleto.
        """
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(dir=destino.parent, prefix=".replay-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write(self.serializar())
            os.replace(temporario, destino)
        except BaseException:
            Path(temporario).unlink(missing_ok=True)
            raise
        return destino
