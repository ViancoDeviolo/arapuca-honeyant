from pathlib import Path
from honeyant.core.rota import ObservadorDeIteracao, Snapshot

class GravadorJson(ObservadorDeIteracao):
    """Adaptador para persistência do replay das iterações do Pathfinder em formato JSONL."""

    def __init__(self, caminho_arquivo: Path | str):
        self.caminho = Path(caminho_arquivo)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # Inicializa ou limpa o arquivo de destino
        self.caminho.write_text("", encoding="utf-8")

    def notificar(self, snapshot: Snapshot) -> None:
        """Recebe um Snapshot do core e grava uma linha JSONL."""
        linha = snapshot.model_dump_json()
        with open(self.caminho, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
