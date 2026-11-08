"""`honeyant-app`: o HoneyAnt.exe (spec do aplicativo ao vivo, seção 3.3).

Abre o painel **só em 127.0.0.1** (portas 8765 a 8774) e o navegador. Os cartões e as
formigas de ataque usam o resumo ao vivo do resumo-api da EC2; sem acesso, o último em cache
("offline") ou o embutido. A rota da demo usa sempre o resumo embutido.

- A **chave de acesso** fica em `%APPDATA%\\HoneyAnt\\config.json` (pedida na primeira vez).
  Dívida técnica: em texto; no futuro, proteger com DPAPI.
- A **URL** (`app.json`) e a **CA** (`ca.crt`) vêm junto do executável; sem elas, o app
  funciona só com o resumo guardado.
"""

import getpass
import json
import os
import re
import socket
import sys
import threading
import webbrowser
from collections.abc import Callable, Mapping
from pathlib import Path

PORTA_INICIAL = 8765
# Chave de acesso: caracteres ASCII visíveis, sem espaço (token_urlsafe usa A-Z a-z 0-9 _ -).
_CHAVE_VALIDA = re.compile(r"^[!-~]{8,256}$")
TENTATIVAS = 10


class PortasOcupadas(RuntimeError):
    pass


def recursos() -> Path:
    """Onde estão `docs/demo`, `app.json` e `ca.crt`: no `.exe`, a pasta do PyInstaller."""
    empacotado = getattr(sys, "_MEIPASS", None)
    return Path(empacotado) if empacotado else Path(__file__).resolve().parents[3]


def pasta_do_usuario() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) / "HoneyAnt" if base else Path.home() / ".config" / "honeyant"


def abrir_socket(inicio: int = PORTA_INICIAL, tentativas: int = TENTATIVAS) -> socket.socket:
    """Socket em 127.0.0.1 (nunca 0.0.0.0) na primeira porta livre da faixa."""
    for porta in range(inicio, inicio + tentativas):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: ninguém divide a porta
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", porta))
        except OSError:
            sock.close()
            continue
        sock.listen()
        return sock
    raise PortasOcupadas(
        f"As portas {inicio} a {inicio + tentativas - 1} estão ocupadas. "
        "Feche outro HoneyAnt aberto e tente de novo."
    )


def ler_chave(config: Path, perguntar: Callable[[str], str] = getpass.getpass) -> str | None:
    """A chave salva; sem ela (ou com o arquivo corrompido), pergunta e salva."""
    try:
        chave = json.loads(config.read_text(encoding="utf-8")).get("chave")
        if isinstance(chave, str) and _CHAVE_VALIDA.match(chave.strip()):
            return chave.strip()
    except (OSError, ValueError, AttributeError):
        pass
    for _tentativa in range(2):
        chave = perguntar(
            "Cole a chave de acesso e tecle Enter (nada aparece enquanto você cola; "
            "só Enter para usar o resumo guardado): "
        ).strip()
        if not chave:
            return None
        if _CHAVE_VALIDA.match(chave):
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps({"chave": chave}), encoding="utf-8")
            print(f"Chave recebida ({len(chave)} caracteres).")
            return chave
        print(
            "Essa chave tem caracteres que não são de uma chave (espaço ou aspas curvas do "
            "WhatsApp?). Copie de novo, só a chave."
        )
    return None


def esquecer_chave(config: Path) -> None:
    """Depois de um 401: a próxima abertura pede a chave de novo (sem repetir a errada)."""
    try:
        config.write_text(json.dumps({}), encoding="utf-8")
    except OSError:
        pass


def abrir_navegador(
    endereco: str,
    env: Mapping[str, str] = os.environ,
    abrir: Callable[[str], object] = webbrowser.open,
    espera_s: float = 1.0,
) -> None:
    """Abre o navegador sozinho, depois que o servidor sobe. `HONEYANT_SEM_NAVEGADOR=1`
    desliga (testes de fumaça do .exe)."""
    if env.get("HONEYANT_SEM_NAVEGADOR"):
        return
    if espera_s <= 0:
        abrir(endereco)
    else:
        threading.Timer(espera_s, abrir, args=(endereco,)).start()


def _ler_url(arquivo: Path) -> str | None:
    try:
        url = json.loads(arquivo.read_text(encoding="utf-8")).get("url", "")
    except (OSError, ValueError, AttributeError):
        return None
    return url if isinstance(url, str) and url.startswith("https://") else None


def main() -> int:
    import uvicorn  # só o app precisa do servidor web

    from honeyant.apps.local import ConfigLocal, FonteDoResumoLocal, montar
    from honeyant.apps.resumo_ao_vivo import ClienteResumo, FonteDoResumoAoVivo, contexto_cliente

    print("HoneyAnt — painel ao vivo")
    try:
        sock = abrir_socket()
    except PortasOcupadas as erro:
        print(erro)
        input("Tecle Enter para fechar.")
        return 1
    porta = sock.getsockname()[1]
    base = recursos()
    demo = base / "docs" / "demo"
    usuario = pasta_do_usuario()

    url, ca = _ler_url(base / "app.json"), base / "ca.crt"
    cliente = None
    if url and ca.is_file():
        chave = ler_chave(usuario / "config.json")
        if chave:
            cliente = ClienteResumo(url, chave, contexto_cliente(ca))
    if cliente is None:
        print("Sem chave ou sem endereço da isca: usando o resumo guardado (offline).")

    fonte_resumo = FonteDoResumoAoVivo(
        cliente,
        usuario / "ultimo-resumo.json",
        FonteDoResumoLocal(demo),
        avisar=lambda mensagem: print(mensagem, flush=True),
        ao_recusar=lambda: esquecer_chave(usuario / "config.json"),
    )
    fonte_resumo.iniciar()  # primeira consulta já na abertura; depois a cada 15 s
    app = montar(ConfigLocal(demo, "127.0.0.1", porta), fonte_resumo=fonte_resumo)
    endereco = f"http://127.0.0.1:{porta}/"
    abrir_navegador(endereco)
    print(f"Painel em {endereco} (abrindo o navegador).")
    print("Feche esta janela para sair.")
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
    return 0


if __name__ == "__main__":
    sys.exit(main())
