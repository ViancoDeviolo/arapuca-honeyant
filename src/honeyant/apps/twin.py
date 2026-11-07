"""`honeyant-twin`: prepara, sobe e derruba a casa simulada (Docker Compose).

    uv run honeyant-twin preparar           # gera senhas, CA, certificados e configs (local)
    uv run honeyant-twin subir [--perfil seguro]
    uv run honeyant-twin descer
    uv run honeyant-twin status

`preparar` grava tudo em `infra/twin/gerado/` (fora do git): os dois perfis prontos, para o
`honeyant-mitigar` trocar de um para o outro sem gerar nada de novo. Os dispositivos saem
da `planejar_dispositivos` (twin/planta.py) e a credencial vazada da câmera, do mesmo
resumo que o painel usa (o real, se houver).
"""

import argparse
import json
import secrets
import shutil
import subprocess  # nosec B404  # só chama o docker, com argumentos em lista e sem shell
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from honeyant.apps.local import FonteDoResumoLocal, _ler_json
from honeyant.core.casa import PerfilDaCasa, TipoDePerfil
from honeyant.twin import configuracao as cfg
from honeyant.twin.planta import planejar_dispositivos

DIR_TWIN = Path("infra/twin")
DEMO_DIR = Path("docs/demo")
PROJETO = "honeyant-twin"
IMAGEM_OPENSSL = (
    "nicolaka/netshoot@sha256:b09d9b21381f47a79b3cbcb30da25266dc17186ea00ae65e99fdc51396f48e70"
)

# CA e certificado do broker, só para a demo (30 dias). A chave da CA é apagada depois de
# assinar: ninguém consegue emitir outro certificado aceito pelos dispositivos.
SCRIPT_CERTIFICADOS = (
    "set -e; cd /w; "
    'openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 30 -subj "/CN=HoneyAnt CA demo" '
    "-keyout ca.key -out ca.crt 2>/dev/null; "
    'openssl req -newkey rsa:2048 -nodes -subj "/CN=broker" -keyout broker.key '
    "-out broker.csr 2>/dev/null; "
    'printf "subjectAltName=DNS:broker\\n" > ext.cnf; '
    "openssl x509 -req -sha256 -days 30 -in broker.csr -CA ca.crt -CAkey ca.key "
    "-CAcreateserial -extfile ext.cnf -out broker.crt 2>/dev/null; "
    "rm -f broker.csr ext.cnf ca.srl ca.key; chmod 644 broker.key ca.crt broker.crt"
)


class ErroDoTwin(RuntimeError):
    """Falha ao preparar ou controlar a casa simulada, com uma mensagem para quem roda."""


Executor = Callable[[Sequence[str]], str]


def executar_docker(argumentos: Sequence[str]) -> str:
    """Roda `docker ...` e devolve a saída; falha com a mensagem do próprio docker."""
    docker = shutil.which("docker")
    if docker is None:
        raise ErroDoTwin("docker não encontrado: instale o Docker Desktop e abra-o")
    # Caminho completo do docker e lista fixa de argumentos, sem shell.
    r = subprocess.run(  # noqa: S603  # nosec B603
        [docker, *argumentos], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise ErroDoTwin(f"docker {' '.join(argumentos[:3])}… falhou:\n{r.stderr.strip()}")
    return r.stdout


def _gerar_senha() -> str:
    return secrets.token_urlsafe(24)  # 32 caracteres de [A-Za-z0-9_-]


class ControleDoTwin:
    def __init__(
        self,
        dir_twin: Path = DIR_TWIN,
        demo_dir: Path = DEMO_DIR,
        docker: Executor = executar_docker,
        gerar_senha: Callable[[], str] = _gerar_senha,
    ) -> None:
        self.dir = dir_twin
        self.demo_dir = demo_dir
        self.docker = docker
        self.gerar_senha = gerar_senha

    @property
    def gerado(self) -> Path:
        return self.dir / "gerado"

    def pasta(self, tipo: TipoDePerfil) -> Path:
        return self.gerado / tipo.value

    def preparar(self) -> None:
        resumo = FonteDoResumoLocal(self.demo_dir).resumo().resumo
        vazada = cfg.credencial_vazada(resumo)
        for tipo in TipoDePerfil:
            perfil = PerfilDaCasa.model_validate(
                _ler_json(self.demo_dir / f"perfil-{tipo.value}.json")
            )
            dispositivos = planejar_dispositivos(perfil)
            usuarios = cfg.credenciais(tipo, dispositivos, vazada, self.gerar_senha)
            pasta = self.pasta(tipo)
            mosquitto = pasta / "mosquitto"
            if pasta.exists():
                shutil.rmtree(pasta)
            mosquitto.mkdir(parents=True)
            (mosquitto / "mosquitto.conf").write_text(cfg.mosquitto_conf(tipo), "utf-8")
            (pasta / ".env").write_text(cfg.env(tipo, usuarios), "utf-8")
            (pasta / "dispositivos.json").write_text(
                json.dumps(cfg.compose_dispositivos(tipo, dispositivos), indent=2), "utf-8"
            )
            if tipo is TipoDePerfil.SEGURO:
                (mosquitto / "acl").write_text(cfg.acl(dispositivos, usuarios), "utf-8")
                (mosquitto / "passwd").write_text(cfg.senhas_para_mosquitto(usuarios), "utf-8")
                self._hash_das_senhas(mosquitto)
                (mosquitto / "certs").mkdir()
                self.docker(
                    ["run", "--rm", "-v", f"{(mosquitto / 'certs').resolve()}:/w",
                     "--entrypoint", "sh", IMAGEM_OPENSSL, "-c", SCRIPT_CERTIFICADOS]
                )  # fmt: skip

    def _hash_das_senhas(self, mosquitto: Path) -> None:
        # Troca "usuario:senha" pelo hash do próprio Mosquitto; o texto puro não fica no disco.
        self.docker(
            ["run", "--rm", "-v", f"{mosquitto.resolve()}:/w", "--entrypoint",
             "mosquitto_passwd", cfg.IMAGEM_MOSQUITTO, "-U", "/w/passwd"]
        )  # fmt: skip

    def _compose(self, tipo: TipoDePerfil, *resto: str, captura: bool = False) -> str:
        pasta = self.pasta(tipo)
        if not (pasta / ".env").is_file():
            raise ErroDoTwin("o twin não foi preparado: rode `uv run honeyant-twin preparar`")
        args = [
            *("compose", "-p", PROJETO, "-f", str(self.dir / "compose.yml")),
            *("-f", str(pasta / "dispositivos.json"), "--env-file", str(pasta / ".env")),
        ]
        if captura:
            args += ["--profile", "captura"]
        return self.docker([*args, *resto])

    def subir(
        self, tipo: TipoDePerfil, servicos: Sequence[str] = (), *, captura: bool = False
    ) -> None:
        self._compose(tipo, "up", "-d", "--force-recreate", *servicos, captura=captura)
        (self.gerado / "ATIVO").write_text(tipo.value, "utf-8")

    def parar(self, tipo: TipoDePerfil, servicos: Sequence[str]) -> None:
        self._compose(tipo, "stop", *servicos, captura=True)

    def descer(self) -> None:
        ativo = self.ativo()
        if ativo is not None:
            self._compose(ativo, "down", "--remove-orphans", captura=True)
            (self.gerado / "ATIVO").unlink(missing_ok=True)

    def ativo(self) -> TipoDePerfil | None:
        arquivo = self.gerado / "ATIVO"
        return TipoDePerfil(arquivo.read_text("utf-8").strip()) if arquivo.is_file() else None

    def status(self) -> str:
        ativo = self.ativo()
        if ativo is None:
            return "twin parado"
        return f"perfil {ativo.value}\n" + self._compose(ativo, "ps", captura=True)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="honeyant-twin", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("preparar", help="gera senhas, CA, certificados e configs dos dois perfis")
    s = sub.add_parser("subir", help="sobe a casa num perfil (padrão: inseguro)")
    s.add_argument("--perfil", choices=[t.value for t in TipoDePerfil], default="inseguro")
    sub.add_parser("descer", help="derruba a casa")
    sub.add_parser("status", help="mostra o perfil ativo e os containers")
    args = p.parse_args(argv)
    twin = ControleDoTwin()
    try:
        if args.comando == "preparar":
            twin.preparar()
            print(f"pronto: {twin.gerado} (fora do git). Suba com `honeyant-twin subir`.")
        elif args.comando == "subir":
            twin.descer()
            twin.subir(TipoDePerfil(args.perfil))
            print(f"casa no ar no perfil {args.perfil}")
        elif args.comando == "descer":
            twin.descer()
            print("casa derrubada")
        else:
            print(twin.status())
    except ErroDoTwin as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
