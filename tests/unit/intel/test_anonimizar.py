"""Máscara de IPv4 no que sai da EC2, e nenhum IPv4 nos resumos versionados."""

import json
import re
from pathlib import Path

import pytest

from honeyant.intel.anonimizar import mascarar_ipv4
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
        ("fim de frase 8.8.8.8.", "fim de frase <ipv4>."),
        ("255.255.255.255", "<ipv4>"),
    ],
)
def test_mascara_ipv4(entrada, esperado):
    assert mascarar_ipv4(entrada) == esperado


@pytest.mark.parametrize(
    "parecido",
    [
        "admin",  # sem IP
        "",
        "xc3511",
        "1.2.3",  # só três partes
        "1.2.3.4.5",  # cinco partes (versão, OID)
        "999.1.1.1",  # octeto acima de 255
        "256.0.0.1",
        "v2.0.1",
        "12345.6.7.8",
        "2001:db8::1",  # IPv6 não é alvo desta função
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
