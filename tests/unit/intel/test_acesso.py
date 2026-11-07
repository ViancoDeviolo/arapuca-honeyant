"""Chave de acesso do resumo-api: hash scrypt, tempo constante e 5 erros / 15 min por IP."""

import hmac

import pytest

from honeyant.apps import chave_app
from honeyant.intel import acesso
from honeyant.intel.acesso import ControleDeAcesso, gerar_hash, hash_valido

CHAVE = "chave-de-teste-com-tamanho-razoavel"
HASH = gerar_hash(CHAVE)
IP, OUTRO_IP = "203.0.113.7", "198.51.100.9"


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def controle(relogio):
    return ControleDeAcesso(HASH, relogio=relogio)


def test_chave_certa_ok(controle):
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "ok"


def test_sem_cabecalho_negado(controle):
    assert controle.verificar(IP, None) == "negado"


@pytest.mark.parametrize("cabecalho", ["Basic x", "Bearer", "", f"bearer{CHAVE}"])
def test_bearer_malformado_negado(controle, cabecalho):
    assert controle.verificar(IP, cabecalho) == "negado"


def test_quinto_erro_bloqueia_por_15_min(controle, relogio):
    for _ in range(5):
        assert controle.verificar(IP, "Bearer errada") == "negado"
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "bloqueado"
    relogio.t += 899
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "bloqueado"
    relogio.t += 2  # 901 s depois do bloqueio
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "ok"


def test_erros_de_outro_ip_nao_bloqueiam(controle):
    for _ in range(5):
        controle.verificar(OUTRO_IP, "Bearer errada")
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "ok"
    assert controle.verificar(OUTRO_IP, f"Bearer {CHAVE}") == "bloqueado"


def test_erros_fora_da_janela_nao_somam(controle, relogio):
    for _ in range(4):
        controle.verificar(IP, "Bearer errada")
    relogio.t += 901
    for _ in range(4):
        assert controle.verificar(IP, "Bearer errada") == "negado"
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "ok"


def test_compara_em_tempo_constante(controle, monkeypatch):
    chamadas = []
    original = hmac.compare_digest

    def espiao(a, b):
        chamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(acesso.hmac, "compare_digest", espiao)
    controle.verificar(IP, f"Bearer {CHAVE}")
    controle.verificar(IP, "Bearer errada")
    assert len(chamadas) == 2


def test_hash_valido():
    assert hash_valido(HASH)
    assert not hash_valido("x")
    assert not hash_valido("bcrypt$16384$8$1$AAAA$AAAA")
    assert not hash_valido("scrypt$16384$8$1$AAAA")


def test_hash_invalido_no_controle_e_recusado():
    with pytest.raises(ValueError, match="honeyant-chave-app"):
        ControleDeAcesso("nao-e-hash")


def test_chave_app_imprime_chave_e_hash_que_confere(capsys, relogio):
    chave_app.main()
    linhas = [linha for linha in capsys.readouterr().out.splitlines() if linha.strip()]
    chave = next(linha.split(":", 1)[1].strip() for linha in linhas if linha.startswith("Chave"))
    hash_linha = next(linha for linha in linhas if linha.startswith("HONEYANT_RESUMO_CHAVE_HASH="))
    hash_salvo = hash_linha.split("=", 1)[1]
    assert len(chave) >= 40
    assert ControleDeAcesso(hash_salvo, relogio=relogio).verificar(IP, f"Bearer {chave}") == "ok"
