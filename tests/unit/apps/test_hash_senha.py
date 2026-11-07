"""`honeyant-hash-senha`: lê a senha sem ecoar e imprime só o hash."""

import pytest

from honeyant.apps.hash_senha import main
from honeyant.painel.autenticacao import verificar_senha

SENHA = "senha-de-teste-123"  # noqa: S105  (valor falso, só para os testes)


def _leitor(*respostas):
    fila = list(respostas)
    return lambda _pergunta="": fila.pop(0)


def test_imprime_so_o_hash_e_ele_confere(capsys):
    assert main([], ler=_leitor(SENHA, SENHA)) == 0
    saida = capsys.readouterr()
    hash_impresso = saida.out.strip()
    assert hash_impresso.startswith("scrypt$") and "\n" not in hash_impresso
    assert verificar_senha(SENHA, hash_impresso) is True
    assert SENHA not in saida.out and SENHA not in saida.err


def test_senhas_diferentes_nao_geram_hash(capsys):
    assert main([], ler=_leitor(SENHA, SENHA + "x")) == 1
    saida = capsys.readouterr()
    assert saida.out == "" and "não conferem" in saida.err


def test_senha_com_menos_de_12_caracteres_e_recusada(capsys):
    assert main([], ler=_leitor("onze-chars!", "onze-chars!")) == 1
    saida = capsys.readouterr()
    assert saida.out == "" and "12" in saida.err


def test_senha_nunca_vem_por_argumento_de_linha_de_comando():
    with pytest.raises(SystemExit) as erro:
        main([SENHA], ler=_leitor(SENHA, SENHA))
    assert erro.value.code == 2
