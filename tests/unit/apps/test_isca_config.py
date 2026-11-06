from pathlib import Path

from honeyant.apps.isca import ConfigIsca, montar_geo


def test_padroes():
    c = ConfigIsca.do_ambiente({})
    assert (c.db, c.porta_telnet, c.porta_mqtt) == (Path("/dados/isca.db"), 2323, 18830)
    assert c.geo_dir == Path("/geo")


def test_sobrescreve_por_ambiente():
    c = ConfigIsca.do_ambiente({"HONEYANT_DB": "x.db", "HONEYANT_PORTA_MQTT": "1999"})
    assert c.db == Path("x.db") and c.porta_mqtt == 1999


def test_sem_base_geo_usa_geo_nulo(tmp_path):
    assert montar_geo(tmp_path).resolver("203.0.113.7") == (None, None)
