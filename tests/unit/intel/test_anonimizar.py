"""Máscara de IPv4 no que sai da EC2, e nenhum IPv4 nos resumos versionados."""

import json
import random
import re
from pathlib import Path

import pytest

from honeyant.intel.anonimizar import MASCARA, mascarar_ipv4
from honeyant.intel.resumo import agregar

DEMO = Path(__file__).parents[3] / "docs" / "demo"
# Bem mais largo que o da máscara, de propósito: pega qualquer coisa com cara de IPv4.
QUALQUER_IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("MGLNDD_203.0.113.7_23", "MGLNDD_<ipv4>_23"),  # no meio do texto
        ("1.2.3.4", "<ipv4>"),
        ("de 10.0.0.1 para 192.168.0.254", "de <ipv4> para <ipv4>"),  # vários
        ("fim de frase 192.0.2.1.", "fim de frase <ipv4>."),
        ("255.255.255.255", "<ipv4>"),
        # Formas que escapavam até 09/11 (auditoria final, L1):
        ("054.175.090.121", "<ipv4>"),  # zeros à esquerda
        ("000.000.000.000", "<ipv4>"),
        ("54.175.90.121.23", "<ipv4>.23"),  # IP seguido de .porta
        ("ec2-54-175-90-121", "ec2-<ipv4>"),  # hífens (host da AWS)
        ("ec2-54-175-90-121.compute-1.amazonaws.com", "ec2-<ipv4>.compute-1.amazonaws.com"),
        ("ip-172-31-0-5", "ip-<ipv4>"),
        ("54-175-90-121-23", "<ipv4>-23"),
        # Privacidade acima de falso positivo: até 09/11 este caso ficava intacto (era
        # tratado como versão/OID). Agora os quatro primeiros números são mascarados.
        ("1.2.3.4.5", "<ipv4>.5"),
    ],
)
def test_mascara_ipv4(entrada, esperado):
    assert mascarar_ipv4(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("MGLNDD_203.0.113.7_23", "MGLNDD_<ipv4>_23"),
        ("203.0.113.7:23", "<ipv4>:23"),
        ("x203.0.113.7x", "x<ipv4>x"),
        ("::ffff:203.0.113.7", "::ffff:<ipv4>"),
        ("203.0.113.7/32", "<ipv4>/32"),
        ("admin@203.0.113.7", "admin@<ipv4>"),
        ("1a203.0.113.7", "1a<ipv4>"),
    ],
)
def test_as_sete_formas_que_ja_funcionavam_continuam(entrada, esperado):
    assert mascarar_ipv4(entrada) == esperado


def _ips_aleatorios(n: int = 40) -> list[tuple[int, int, int, int]]:
    sorteio = random.Random(20261109)  # semente fixa: o mesmo conjunto em todo CI  # noqa: S311
    return [tuple(sorteio.randint(0, 255) for _ in range(4)) for _ in range(n)]


def _formas(ip: tuple[int, int, int, int]) -> dict[str, str]:
    return {
        "zeros": ".".join(f"{o:03d}" for o in ip),
        "porta": ".".join(map(str, ip)) + ".23",
        "hifens": "ec2-" + "-".join(map(str, ip)),
    }


def _rastros(ip: tuple[int, int, int, int]) -> list[str]:
    """Qualquer grafia do IP que não pode sobrar no texto mascarado."""
    return [
        ".".join(map(str, ip)),
        ".".join(f"{o:03d}" for o in ip),
        "-".join(map(str, ip)),
        "-".join(f"{o:03d}" for o in ip),
    ]


@pytest.mark.parametrize("ip", _ips_aleatorios(), ids=lambda ip: ".".join(map(str, ip)))
@pytest.mark.parametrize("forma", ["zeros", "porta", "hifens"])
@pytest.mark.parametrize("molde", ["{}", "MGLNDD_{}_23", "user {} fim", "a@{}"])
def test_nenhum_ipv4_aleatorio_sobra(ip, forma, molde):
    texto = molde.format(_formas(ip)[forma])
    mascarado = mascarar_ipv4(texto)
    assert MASCARA in mascarado
    for rastro in _rastros(ip):
        assert rastro not in mascarado, (texto, mascarado)


@pytest.mark.parametrize(
    "parecido",
    [
        "admin",  # sem IP
        "",
        "xc3511",
        "1.2.3",  # só três partes
        "999.1.1.1",  # octeto acima de 255
        "256.0.0.1",
        "v2.0.1",
        "12345.6.7.8",
        "2001:db8::1",  # IPv6 não é alvo desta função
        "2026-11-09",  # data: só três partes com hífen
        "09-11-2026",
        "2026-11-09-10-20",  # data e hora: os números estão colados a "2026-"
        "1-2-3",
        "999-1-1-1",  # octeto acima de 255
        "10.0.0",
    ],
)
def test_texto_sem_ipv4_fica_igual(parecido):
    assert mascarar_ipv4(parecido) == parecido


def test_agregar_mascara_usuario_e_senha(fabrica_evento, agora):
    eventos = [
        fabrica_evento(usuario="MGLNDD_198.51.100.9_23"),
        fabrica_evento(usuario="root", senha="senha-10.1.2.3"),
    ]
    texto = agregar(eventos, {}, agora).model_dump_json()
    assert "MGLNDD_<ipv4>_23" in texto and "senha-<ipv4>" in texto
    assert not QUALQUER_IPV4.search(texto)


@pytest.mark.parametrize("arquivo", sorted(DEMO.glob("resumo-*.json")), ids=lambda p: p.name)
def test_nenhum_ipv4_nos_resumos_versionados(arquivo):
    texto = arquivo.read_text("utf-8")
    achado = QUALQUER_IPV4.search(texto)
    assert achado is None, f"{arquivo.name} tem algo com cara de IPv4 (rode a máscara do intel)"
    json.loads(texto)  # e continua JSON válido
