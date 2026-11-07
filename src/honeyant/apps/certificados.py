"""`honeyant-certificados`: CA do projeto e certificado do resumo-api (90 dias).

    uv run honeyant-certificados --ip <ip-elastico-da-ec2>

- **CA** (5 anos): criada só se não existir, em `%USERPROFILE%\\.honeyant\\ca\\` (ou
  `~/.honeyant/ca`). A **chave da CA fica só ali**: nunca vai para a EC2 nem para o
  repositório. O `ca.crt` (público) vai embutido no app.
- **Servidor** (90 dias, `subjectAltName = IP:<ip>`): `servidor.crt` e `servidor.key` em
  `infra/certs-resumo/` (fora do git), que vão para a EC2 por `scp`.
- Renovação: rodar de novo com o mesmo `--ip`; a CA é a mesma, então os apps já
  distribuídos continuam aceitando.

Usa o `openssl` do PATH ou o que vem com o Git para Windows.
"""

import argparse
import ipaddress
import shutil
import subprocess  # nosec B404  # só chama o openssl, com argumentos em lista e sem shell
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

DIAS_CA = 5 * 365
DIAS_SERVIDOR = 90
CA_PADRAO = Path.home() / ".honeyant" / "ca"
SAIDA_PADRAO = Path("infra/certs-resumo")
_OPENSSL_DO_GIT = (
    Path(r"C:\Program Files\Git\mingw64\bin\openssl.exe"),
    Path(r"C:\Program Files\Git\usr\bin\openssl.exe"),
)


class ErroDeCertificado(RuntimeError):
    pass


def localizar_openssl() -> str | None:
    achado = shutil.which("openssl")
    if achado:
        return achado
    return next((str(p) for p in _OPENSSL_DO_GIT if p.is_file()), None)


def _openssl(*args: str) -> None:
    openssl = localizar_openssl()
    if openssl is None:
        raise ErroDeCertificado(
            "openssl não encontrado: instale o Git para Windows (ele traz o openssl)"
        )
    r = subprocess.run(  # noqa: S603  # nosec B603  # lista fixa, sem shell
        [openssl, *args], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise ErroDeCertificado(f"openssl {args[0]} falhou:\n{r.stderr.strip()}")


def _config(pasta: Path, nome: str, extensoes: str) -> Path:
    # Arquivo de configuração em vez de -subj: o openssl do Git no Windows pode
    # converter argumentos que começam com "/".
    cnf = pasta / "openssl.cnf"
    cnf.write_text(
        f"[req]\nprompt = no\ndistinguished_name = dn\n[dn]\nCN = {nome}\n[ext]\n{extensoes}\n",
        encoding="ascii",
    )
    return cnf


def gerar_ca(ca_dir: Path) -> None:
    """Cria `ca.key` e `ca.crt` em `ca_dir`, se ainda não existirem."""
    tem_chave, tem_certificado = (ca_dir / "ca.key").is_file(), (ca_dir / "ca.crt").is_file()
    if tem_chave and tem_certificado:
        return
    if tem_chave or tem_certificado:
        # Gerar outra CA invalidaria todos os apps já distribuídos.
        raise ErroDeCertificado(
            f"CA pela metade em {ca_dir} (falta {'ca.crt' if tem_chave else 'ca.key'}): "
            "recupere o arquivo do backup em vez de gerar outra CA"
        )
    if localizar_openssl() is None:
        _openssl("version")  # levanta a mensagem clara
    ca_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cnf = _config(
            Path(tmp),
            "HoneyAnt CA",
            "basicConstraints = critical, CA:TRUE\nkeyUsage = critical, keyCertSign, cRLSign",
        )
        _openssl(
            "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
            "-days", str(DIAS_CA), "-config", str(cnf), "-extensions", "ext",
            "-keyout", str(ca_dir / "ca.key"), "-out", str(ca_dir / "ca.crt"),
        )  # fmt: skip


def emitir(ip: str, ca_dir: Path, saida: Path, dias: int = DIAS_SERVIDOR) -> None:
    """Emite `servidor.crt`/`servidor.key` para o IP, assinados pela CA de `ca_dir`."""
    ipaddress.ip_address(ip)  # ValueError se não for um IP
    if not (ca_dir / "ca.key").is_file():
        raise ErroDeCertificado(f"CA não encontrada em {ca_dir}: rode sem --ca-dir ou crie a CA")
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cnf = _config(
            Path(tmp),
            "honeyant-resumo",
            f"subjectAltName = IP:{ip}\nextendedKeyUsage = serverAuth\n"
            "basicConstraints = critical, CA:FALSE",
        )
        csr = Path(tmp) / "servidor.csr"
        _openssl(
            "req", "-new", "-newkey", "rsa:2048", "-nodes", "-config", str(cnf),
            "-keyout", str(saida / "servidor.key"), "-out", str(csr),
        )  # fmt: skip
        _openssl(
            "x509", "-req", "-sha256", "-days", str(dias), "-in", str(csr),
            "-CA", str(ca_dir / "ca.crt"), "-CAkey", str(ca_dir / "ca.key"),
            "-CAcreateserial", "-CAserial", str(Path(tmp) / "ca.srl"),
            "-extfile", str(cnf), "-extensions", "ext", "-out", str(saida / "servidor.crt"),
        )  # fmt: skip


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="honeyant-certificados", description=__doc__.splitlines()[0])
    p.add_argument("--ip", required=True, help="IP elástico da EC2")
    p.add_argument("--ca-dir", type=Path, default=CA_PADRAO)
    p.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = p.parse_args(argv)
    try:
        gerar_ca(args.ca_dir)
        emitir(args.ip, args.ca_dir, args.saida)
    except (ErroDeCertificado, ValueError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    print(f"CA (fica só aqui): {args.ca_dir}")
    print(f"Servidor, 90 dias, para {args.ip}: {args.saida}/servidor.crt e servidor.key")
    print("Copie a pasta para a EC2 (DEPLOY, seção 7.2). O ca.crt vai no build do app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
