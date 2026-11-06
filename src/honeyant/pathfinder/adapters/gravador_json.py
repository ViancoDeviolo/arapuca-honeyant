"""Persistência de snapshots do ACO em JSONL."""

from pathlib import Path

from honeyant.core.rota import Snapshot


class GravadorJson:
    """Adaptador de replay: grava um snapshot por linha em `.jsonl`."""

    def __init__(self, caminho_arquivo: Path | str) -> None:
        self.caminho = Path(caminho_arquivo)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text("", encoding="utf-8")

    def notificar(self, snapshot: Snapshot) -> None:
        """Recebe o Snapshot do core e grava uma linha no arquivo JSONL."""
        with self.caminho.open("a", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(snapshot.model_dump_json())
            arquivo.write("\n")
