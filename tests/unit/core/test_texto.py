from honeyant.core.texto import limpar


def test_remove_controles_e_escape_ansi():
    assert limpar("ad\x00min\x1b[31m", 64) == "admin[31m"


def test_trunca_no_limite():
    assert limpar("a" * 100, 64) == "a" * 64


def test_preserva_unicode_imprimivel():
    # escapar é papel de quem exibe; aqui o texto só é limpo e truncado
    assert limpar("senha<script>çã", 64) == "senha<script>çã"
