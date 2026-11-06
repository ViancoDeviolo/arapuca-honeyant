from honeyant.arapuca.limites import Limitador


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_limite_por_ip_e_liberacao():
    lim = Limitador(max_por_ip=2)
    assert lim.entrar("1.1.1.1") and lim.entrar("1.1.1.1")
    assert not lim.entrar("1.1.1.1")
    lim.sair("1.1.1.1")
    assert lim.entrar("1.1.1.1")


def test_limite_total():
    lim = Limitador(max_total=2, max_por_ip=5)
    assert lim.entrar("1.1.1.1") and lim.entrar("2.2.2.2")
    assert not lim.entrar("3.3.3.3")


def test_taxa_por_minuto_reinicia_apos_60s():
    rel = Relogio()
    lim = Limitador(max_por_ip=100, taxa_por_minuto=3, relogio=rel)
    for _ in range(3):
        assert lim.entrar("1.1.1.1")
        lim.sair("1.1.1.1")
    assert not lim.entrar("1.1.1.1")
    rel.t = 61.0
    assert lim.entrar("1.1.1.1")


def test_ips_inativos_sao_esquecidos():
    rel = Relogio()
    lim = Limitador(relogio=rel)
    lim.entrar("1.1.1.1")
    lim.sair("1.1.1.1")
    rel.t = 61.0
    lim.entrar("2.2.2.2")
    assert lim.ips_rastreados() == 1
