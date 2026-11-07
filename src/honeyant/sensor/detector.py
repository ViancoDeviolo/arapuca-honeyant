"""Detector: do tráfego para `EvidenciaDeRede` (vulnerabilidade identificada, não declarada).

Regra: um `CONNECT` MQTT legível numa porta de MQTT sem TLS (1883) é **texto puro** na
aresta entre aquele dispositivo e o broker. Se a senha que passou em claro for uma
credencial conhecida (`core/credenciais.py`: as completas do resumo real ∪ as padrão de
fábrica de IoT), a credencial também está **vazada**.

O dispositivo vem do id do cliente MQTT (`camera`, `camera-comando`…), que no twin é o id
do nó. Ids que não batem com nenhum nó do perfil são ignorados.
"""

from collections.abc import Iterable, Set

from honeyant.core.casa import PerfilDaCasa, TipoDeNo
from honeyant.core.evidencia import EvidenciaDeRede, Fonte
from honeyant.sensor.mqtt import ler_connect
from honeyant.sensor.ports import FonteDeTrafego

PORTAS_MQTT_SEM_TLS = frozenset({1883})


def _no_do_cliente(id_cliente: str, ids: Iterable[str]) -> str | None:
    for id_ in sorted(ids, key=len, reverse=True):
        if id_cliente == id_ or id_cliente.startswith(f"{id_}-"):
            return id_
    return None


def _arestas_com_o_broker(perfil: PerfilDaCasa) -> dict[str, str]:
    """Para cada nó ligado ao broker, a chave da aresta entre eles (na direção do perfil)."""
    brokers = {n.id for n in perfil.nos if n.tipo is TipoDeNo.BROKER}
    saida = {}
    for a in perfil.arestas:
        if a.destino in brokers:
            saida[a.origem] = f"{a.origem}->{a.destino}"
        elif a.origem in brokers:
            saida[a.destino] = f"{a.origem}->{a.destino}"
    return saida


def detectar(
    fonte: FonteDeTrafego,
    perfil: PerfilDaCasa,
    credenciais_vazadas: Set[tuple[str, str]] = frozenset(),
    portas: Set[int] = PORTAS_MQTT_SEM_TLS,
) -> list[EvidenciaDeRede]:
    """Uma evidência passiva por aresta, com o horário do primeiro `CONNECT` visto."""
    arestas = _arestas_com_o_broker(perfil)
    vistas: dict[str, EvidenciaDeRede] = {}
    for s in fonte.segmentos():
        if s.porta_destino not in portas:
            continue
        connect = ler_connect(s.dados)
        if connect is None:
            continue
        no = _no_do_cliente(connect.id_cliente, arestas)
        if no is None:
            continue
        aresta = arestas[no]
        vazada = None
        if connect.usuario is not None and connect.senha is not None:
            vazada = (connect.usuario, connect.senha) in credenciais_vazadas
        anterior = vistas.get(aresta)
        if anterior is None or (vazada and not anterior.credencial_vazada):
            vistas[aresta] = EvidenciaDeRede(
                aresta=aresta,
                observado_em=anterior.observado_em if anterior else s.instante,
                fonte=Fonte.PASSIVO,
                texto_puro=True,
                credencial_vazada=vazada,
            )
    return sorted(vistas.values(), key=lambda e: e.aresta)
