"""Chave colada errada é recusada no próprio PC, sem gastar tentativa no servidor.

Em 07/11 o Lucas se bloqueou por 15 min colando o rótulo e o hash no lugar da chave.
"""

import pytest

from honeyant.apps.chave_colada import problema_na_chave

CHAVE = "Zq3_kP9-xYb2LmN8vRt5WcA1sDf6GhJ4KlQ0oEuI7yT"


def test_chave_de_verdade_passa():
    assert problema_na_chave(CHAVE) is None


@pytest.mark.parametrize(
    ("colado", "trecho"),
    [
        (f"Chave de acesso (entregue a cada pessoa por fora): {CHAVE}", "rótulo"),
        ("Chave de acesso", "rótulo"),
        ("HONEYANT_RESUMO_CHAVE_HASH='scrypt$16384$8$1$abc$def'", "hash"),
        ("scrypt$16384$8$1$abc$def", "hash"),
        (f"{CHAVE} {CHAVE}", "espaços"),
        (f"'{CHAVE}'", "aspas"),
        (f'"{CHAVE}"', "aspas"),
        (f"“{CHAVE}”", "aspas"),
        (f"{CHAVE}\t", "espaços"),
    ],
)
def test_colagens_erradas_sao_recusadas_com_motivo(colado, trecho):
    motivo = problema_na_chave(colado)
    assert motivo is not None
    assert trecho in motivo


def test_toda_recusa_diz_o_que_fazer():
    for colado in ("Chave de acesso: x", "scrypt$1", "a b", "'a'"):
        assert "Cole de novo só a chave" in problema_na_chave(colado)


def test_conferir_resumo_recusa_sem_abrir_conexao(monkeypatch, capsys):
    from honeyant.apps import conferir_resumo

    def nao_conecta(*_a, **_k):
        pytest.fail("a chave errada não podia sair do PC")

    monkeypatch.setattr(conferir_resumo.urllib.request, "build_opener", nao_conecta)
    url = ["--url", "https://203.0.113.10"]
    assert conferir_resumo.main(url, chave="HONEYANT_RESUMO_CHAVE_HASH='scrypt$1'") == 2
    assert "hash" in capsys.readouterr().out
