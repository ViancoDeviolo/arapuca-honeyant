import importlib

MODULOS = ["core", "arapuca", "intel", "twin", "sensor", "pathfinder", "painel", "apps"]


def test_pacote_tem_versao():
    import honeyant

    assert honeyant.__version__ == "0.1.0"


def test_todos_os_modulos_importam():
    for nome in MODULOS:
        importlib.import_module(f"honeyant.{nome}")
