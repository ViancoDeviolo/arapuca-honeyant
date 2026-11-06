from honeyant.arapuca.adapters.geo import GeoDbIp, GeoNulo


def test_geo_nulo():
    assert GeoNulo().resolver("203.0.113.7") == (None, None)


def test_geo_dbip_le_registros(monkeypatch, tmp_path):
    class Leitor:
        def __init__(self, dados):
            self.dados = dados

        def get(self, ip):
            return self.dados

    leitores = iter(
        [Leitor({"country": {"iso_code": "BR"}}), Leitor({"autonomous_system_number": 28573})]
    )
    monkeypatch.setattr("maxminddb.open_database", lambda caminho: next(leitores))
    geo = GeoDbIp(tmp_path / "p.mmdb", tmp_path / "a.mmdb")
    assert geo.resolver("203.0.113.7") == ("BR", 28573)


def test_geo_dbip_ip_invalido_devolve_none(monkeypatch, tmp_path):
    class Leitor:
        def get(self, ip):
            raise ValueError("ip invalido")

    monkeypatch.setattr("maxminddb.open_database", lambda caminho: Leitor())
    assert GeoDbIp(tmp_path / "p", tmp_path / "a").resolver("lixo") == (None, None)


def test_geo_dbip_ip_sem_registro(monkeypatch, tmp_path):
    class Leitor:
        def get(self, ip):
            return None

    monkeypatch.setattr("maxminddb.open_database", lambda caminho: Leitor())
    assert GeoDbIp(tmp_path / "p", tmp_path / "a").resolver("10.0.0.1") == (None, None)
