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
    hash_salvo = hash_linha.split("=", 1)[1].strip("'")  # o compose remove as aspas
    assert len(chave) >= 40
    assert ControleDeAcesso(hash_salvo, relogio=relogio).verificar(IP, f"Bearer {chave}") == "ok"


def test_linha_do_env_vem_entre_aspas_simples(capsys):
    """O Docker Compose interpreta "$" no env_file: sem aspas simples, o hash chega
    corrompido na EC2 (conferido em 07/11 com o compose real)."""
    chave_app.main()
    linha = next(
        linha
        for linha in capsys.readouterr().out.splitlines()
        if linha.startswith("HONEYANT_RESUMO_CHAVE_HASH=")
    )
    valor = linha.split("=", 1)[1]
    assert valor.startswith("'scrypt$") and valor.endswith("'")


# ---------- menores da revisão final: trava e memória do scrypt ----------


def test_erros_simultaneos_nao_se_perdem(monkeypatch):
    """Sem trava, threads concorrentes sobrescreviam a lista de erros e o bloqueio não
    acontecia no 5º erro."""
    import threading
    import time as _time

    class DictLento(dict):
        def get(self, *args):
            valor = super().get(*args)
            _time.sleep(0.02)  # abre a janela da corrida entre ler e gravar a lista de erros
            return valor

    controle = ControleDeAcesso(HASH, relogio=lambda: 1000.0)
    controle._erros = DictLento()
    monkeypatch.setattr(acesso, "_scrypt", lambda *a: b"x" * 32)  # rápido; a corrida é no estado
    threads = [
        threading.Thread(target=controle.verificar, args=(IP, "Bearer errada")) for _ in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert controle.verificar(IP, f"Bearer {CHAVE}") == "bloqueado"


def test_no_maximo_2_scrypt_ao_mesmo_tempo(monkeypatch):
    """Cada scrypt usa ~16 MiB; o resumo-api tem 128 MiB."""
    import threading
    import time as _time

    ativos, maximo, trava = [0], [0], threading.Lock()
    original = acesso._scrypt

    def scrypt_lento(*args):
        with trava:
            ativos[0] += 1
            maximo[0] = max(maximo[0], ativos[0])
        _time.sleep(0.05)
        with trava:
            ativos[0] -= 1
        return original(*args)

    monkeypatch.setattr(acesso, "_scrypt", scrypt_lento)
    controle = ControleDeAcesso(HASH)
    threads = [
        threading.Thread(target=controle.verificar, args=(f"10.0.0.{i}", f"Bearer {CHAVE}"))
        for i in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert maximo[0] <= acesso.SCRYPT_SIMULTANEOS == 2
