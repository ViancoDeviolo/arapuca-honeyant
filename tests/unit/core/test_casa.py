import pytest
from pydantic import ValidationError

from honeyant.core.casa import Aresta, No, PerfilDaCasa, chave_aresta
from honeyant.core.eventos import Servico


def _no(id_: str, tipo: str, **extra) -> dict:
    return {
        "id": id_,
        "tipo": tipo,
        "rotulo": id_.title(),
        "x": 0,
        "y": 0,
        "sensibilidade": 5,
    } | extra


def _perfil(**extra) -> dict:
    padrao = {
        "perfil": "inseguro",
        "nos": [
            _no("internet", "internet"),
            _no("camera", "camera"),
            _no("fechadura", "fechadura"),
        ],
        "arestas": [
            {
                "origem": "internet",
                "destino": "camera",
                "servico": "telnet",
                "exposicao": 9,
                "fraqueza_fixa": 8,
            },
            {"origem": "camera", "destino": "fechadura", "servico": "mqtt", "exposicao": 4},
        ],
    }
    return padrao | extra


def test_perfil_minimo_valido():
    p = PerfilDaCasa(**_perfil())
    assert p.origem == "internet" and p.alvo == "fechadura"
    assert p.arestas[0].servico is Servico.TELNET
    assert p.arestas[1].fraqueza_fixa is None


def test_chave_da_aresta():
    assert chave_aresta("camera", "broker") == "camera->broker"
    a = Aresta(origem="camera", destino="broker", servico="mqtt", exposicao=6)
    assert a.chave == "camera->broker"


def test_rejeita_aresta_para_no_inexistente():
    arestas = [{"origem": "internet", "destino": "geladeira", "servico": "lan", "exposicao": 1}]
    with pytest.raises(ValidationError, match="geladeira"):
        PerfilDaCasa(**_perfil(arestas=arestas))


def test_rejeita_ids_de_no_duplicados():
    nos = [_no("internet", "internet"), _no("fechadura", "fechadura"), _no("fechadura", "camera")]
    with pytest.raises(ValidationError, match="duplicado"):
        PerfilDaCasa(**_perfil(nos=nos, arestas=[]))


def test_rejeita_aresta_duplicada():
    a = {"origem": "internet", "destino": "camera", "servico": "telnet", "exposicao": 9}
    with pytest.raises(ValidationError, match="duplicada"):
        PerfilDaCasa(**_perfil(arestas=[a, a]))


def test_exige_nos_de_origem_e_alvo():
    nos = [_no("internet", "internet"), _no("camera", "camera")]
    with pytest.raises(ValidationError, match="fechadura"):
        PerfilDaCasa(**_perfil(nos=nos, arestas=[]))


def test_rejeita_laco():
    a = {"origem": "camera", "destino": "camera", "servico": "mqtt", "exposicao": 1}
    with pytest.raises(ValidationError):
        Aresta(**a)


@pytest.mark.parametrize(
    "campo,valor", [("exposicao", 11), ("exposicao", -1), ("fraqueza_fixa", 11)]
)
def test_escalas_de_0_a_10(campo, valor):
    a = {"origem": "a", "destino": "b", "servico": "lan", "exposicao": 5} | {campo: valor}
    with pytest.raises(ValidationError):
        Aresta(**a)


@pytest.mark.parametrize("id_", ["Camera", "câmera", "a->b", "", "x" * 33, "1abc"])
def test_id_de_no_restrito(id_):
    with pytest.raises(ValidationError):
        No(**_no(id_, "camera"))


def test_rejeita_campo_desconhecido():
    with pytest.raises(ValidationError):
        PerfilDaCasa(**_perfil(senha_da_camera="123456"))


def test_perfil_e_imutavel():
    p = PerfilDaCasa(**_perfil())
    with pytest.raises(ValidationError):
        p.perfil = "seguro"
