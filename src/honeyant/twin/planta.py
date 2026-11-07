"""Planta da casa simulada: quais dispositivos o twin sobe e em quais tópicos MQTT cada um fala.

Função pura sobre o contrato `PerfilDaCasa` (zero I/O): quem lê o perfil do disco ou fala
MQTT fica em `adapters/`. Importa só `honeyant.core`, como manda a regra de dependência.
"""

from dataclasses import dataclass

from honeyant.core.casa import PerfilDaCasa, TipoDeNo

# Os 5 dispositivos que falam MQTT. Internet é a origem; roteador e broker são infraestrutura.
TIPOS_DE_DISPOSITIVO = (
    TipoDeNo.CAMERA,
    TipoDeNo.LAMPADA,
    TipoDeNo.TOMADA,
    TipoDeNo.TERMOSTATO,
    TipoDeNo.FECHADURA,
)


class PerfilInvalidoParaTwin(ValueError):
    """O perfil é válido para o core, mas não descreve uma casa que o twin consiga subir."""


@dataclass(frozen=True)
class DispositivoPlanejado:
    """Um dispositivo a subir. Imutável: o ACL do Mosquitto sai daqui, não pode mudar depois."""

    id: str
    tipo: TipoDeNo
    topico_estado: str  # o dispositivo publica só aqui
    topico_comando: str  # o dispositivo assina só este


def topico_estado(id_: str) -> str:
    """Tópico onde o dispositivo publica o próprio estado.

    O `id_` já vem restrito pelo core (minúsculas, dígitos e "_"), então não carrega
    "/", "+" nem "#": não dá para forjar um tópico de outro dispositivo.
    """
    return f"casa/{id_}/estado"


def topico_comando(id_: str) -> str:
    """Tópico que o dispositivo assina para receber comandos (o único que ele assina)."""
    return f"casa/{id_}/comando"


def planejar_dispositivos(perfil: PerfilDaCasa) -> list[DispositivoPlanejado]:
    """Lista os dispositivos que o twin sobe, na ordem do perfil.

    Falha cedo se o perfil não tiver exatamente um broker, se faltar ou sobrar algum dos 5
    dispositivos, ou se algum não tiver ligação com o broker: melhor recusar na partida do
    que subir uma casa pela metade na hora da demonstração.
    """
    broker = _id_do_broker(perfil)
    por_tipo = {t: [n for n in perfil.nos if n.tipo is t] for t in TIPOS_DE_DISPOSITIVO}

    faltando = [t.value for t, nos in por_tipo.items() if not nos]
    if faltando:
        raise PerfilInvalidoParaTwin(f"faltam dispositivos: {', '.join(faltando)}")
    repetidos = [t.value for t, nos in por_tipo.items() if len(nos) > 1]
    if repetidos:
        raise PerfilInvalidoParaTwin(f"mais de um dispositivo do tipo: {', '.join(repetidos)}")

    ligados = _ligados_a(perfil, broker)
    soltos = [n.id for nos in por_tipo.values() for n in nos if n.id not in ligados]
    if soltos:
        raise PerfilInvalidoParaTwin(f"dispositivos sem ligação com o broker: {', '.join(soltos)}")

    return [
        DispositivoPlanejado(
            id=n.id,
            tipo=n.tipo,
            topico_estado=topico_estado(n.id),
            topico_comando=topico_comando(n.id),
        )
        for n in perfil.nos
        if n.tipo in TIPOS_DE_DISPOSITIVO
    ]


def _id_do_broker(perfil: PerfilDaCasa) -> str:
    brokers = [n.id for n in perfil.nos if n.tipo is TipoDeNo.BROKER]
    if len(brokers) != 1:
        raise PerfilInvalidoParaTwin(f"o perfil precisa de um único broker, tem {len(brokers)}")
    return brokers[0]


def _ligados_a(perfil: PerfilDaCasa, no: str) -> set[str]:
    """Ids dos nós com uma aresta para `no` ou vinda dele (a direção não importa aqui)."""
    vizinhos: set[str] = set()
    for a in perfil.arestas:
        if a.origem == no:
            vizinhos.add(a.destino)
        elif a.destino == no:
            vizinhos.add(a.origem)
    return vizinhos
