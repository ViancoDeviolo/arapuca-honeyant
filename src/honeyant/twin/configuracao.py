"""Configuração da casa simulada, gerada a partir da planta (funções puras, zero I/O).

Dois perfis, como no spec-mãe (seção 10):

- **inseguro:** Mosquitto na 1883, sem TLS, sem autenticação e sem ACL. A câmera usa a
  credencial que os atacantes mais tentaram na isca: é ela que aparece legível no
  `antes.pcap`.
- **seguro:** Mosquitto na 8883 com TLS, senha forte e aleatória por dispositivo, ACL por
  tópico (cada um publica só o próprio estado e assina só o próprio comando) e a câmera
  numa rede Docker separada.

Quem grava arquivos e chama o Docker é o `apps/twin.py`; aqui só se monta o texto.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from honeyant.core.casa import TipoDePerfil
from honeyant.core.resumo import ResumoDeAmeaca
from honeyant.twin.planta import DispositivoPlanejado

# Mesma imagem fixada no teste de captura (infra/teste-captura): sem tag flutuante.
IMAGEM_MOSQUITTO = (
    "eclipse-mosquitto:2.0.20"
    "@sha256:21421af7b32bf9ce508e9090c8eb13bb81f410ca778dc205506180a6f862d0eb"
)
PORTA = {TipoDePerfil.INSEGURO: 1883, TipoDePerfil.SEGURO: 8883}
REDE_CASA = "casa"
REDE_CAMERA = "camera_isolada"
USUARIO_MONITOR = "monitor"  # só lê casa/#: usado pelos testes de integração e na demo
INTERVALO_S = 3

# A credencial vem da internet (isca): só entra se for segura para .env e shell.
_CREDENCIAL_SEGURA = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
CREDENCIAL_PADRAO = ("admin", "admin")


@dataclass(frozen=True)
class Credencial:
    usuario: str
    senha: str


def credencial_vazada(resumo: ResumoDeAmeaca) -> Credencial:
    """A credencial mais tentada na isca que dá para usar com segurança (spec-mãe, 10).

    Vem de atacantes: qualquer caractere fora de `[A-Za-z0-9._@-]` (espaço, aspas, `$`,
    quebra de linha) faz a credencial ser pulada, para nunca virar comando no shell nem
    variável no compose.
    """
    for c in resumo.top_credenciais:
        if c.usuario and c.senha and all(_CREDENCIAL_SEGURA.match(v) for v in (c.usuario, c.senha)):
            return Credencial(c.usuario, c.senha)
    return Credencial(*CREDENCIAL_PADRAO)


def credenciais(
    tipo: TipoDePerfil,
    dispositivos: Sequence[DispositivoPlanejado],
    vazada: Credencial,
    gerar_senha: Callable[[], str],
) -> dict[str, Credencial]:
    """Usuário e senha de cada dispositivo (e do monitor), por id."""
    if tipo is TipoDePerfil.INSEGURO:
        # Senha fraca e previsível: a câmera com a vazada, os outros com o próprio id.
        saida = {d.id: Credencial(d.id, d.id) for d in dispositivos}
        saida["camera"] = vazada
        saida[USUARIO_MONITOR] = Credencial(USUARIO_MONITOR, USUARIO_MONITOR)
        return saida
    saida = {d.id: Credencial(d.id, gerar_senha()) for d in dispositivos}
    saida[USUARIO_MONITOR] = Credencial(USUARIO_MONITOR, gerar_senha())
    return saida


def acl(dispositivos: Sequence[DispositivoPlanejado], usuarios: dict[str, Credencial]) -> str:
    """ACL do Mosquitto: cada dispositivo escreve só o estado e lê só o comando dele."""
    linhas = ["# Gerado por honeyant-twin preparar. Cada usuário só vê os tópicos dele.", ""]
    for d in dispositivos:
        linhas += [
            f"user {usuarios[d.id].usuario}",
            f"topic write {d.topico_estado}",
            f"topic read {d.topico_comando}",
            "",
        ]
    linhas += [f"user {usuarios[USUARIO_MONITOR].usuario}", "topic read casa/#", ""]
    return "\n".join(linhas)


def mosquitto_conf(tipo: TipoDePerfil) -> str:
    if tipo is TipoDePerfil.INSEGURO:
        return "\n".join(
            [
                "# Perfil INSEGURO (de propósito): texto puro, sem autenticação e sem ACL.",
                f"listener {PORTA[tipo]}",
                "allow_anonymous true",
                "log_dest stdout",
                "",
            ]
        )
    return "\n".join(
        [
            "# Perfil SEGURO: TLS, senha por dispositivo e ACL por tópico.",
            f"listener {PORTA[tipo]}",
            "cafile /mosquitto/config/certs/ca.crt",
            "certfile /mosquitto/config/certs/broker.crt",
            "keyfile /mosquitto/config/certs/broker.key",
            "tls_version tlsv1.2",
            "allow_anonymous false",
            "password_file /mosquitto/config/passwd",
            "acl_file /mosquitto/config/acl",
            "log_dest stdout",
            "",
        ]
    )


def _variavel(id_: str, campo: str) -> str:
    return f"{campo}_{id_.upper()}"


def compose_dispositivos(tipo: TipoDePerfil, dispositivos: Sequence[DispositivoPlanejado]) -> dict:
    """Serviços do compose, um por dispositivo. As senhas ficam no .env, não aqui."""
    seguro = tipo is TipoDePerfil.SEGURO
    servicos = {}
    for d in dispositivos:
        ambiente = {
            "ID": d.id,
            "MQTT_HOST": "broker",
            "MQTT_PORTA": str(PORTA[tipo]),
            "MQTT_USUARIO": f"${{{_variavel(d.id, 'USUARIO')}}}",
            "MQTT_SENHA": f"${{{_variavel(d.id, 'SENHA')}}}",
            "TOPICO_ESTADO": d.topico_estado,
            "TOPICO_COMANDO": d.topico_comando,
            "INTERVALO": str(INTERVALO_S),
        }
        volumes = ["./dispositivo.sh:/dispositivo.sh:ro"]
        if seguro:
            ambiente["MQTT_CAFILE"] = "/certs/ca.crt"
            volumes.append("./gerado/seguro/mosquitto/certs/ca.crt:/certs/ca.crt:ro")
        isolada = seguro and d.id == "camera"
        servicos[d.id] = {
            "image": IMAGEM_MOSQUITTO,
            "entrypoint": ["/bin/sh", "/dispositivo.sh"],
            "environment": ambiente,
            "volumes": volumes,
            "networks": [REDE_CAMERA if isolada else REDE_CASA],
            "depends_on": ["broker"],
            "restart": "unless-stopped",
        }
    return {"services": servicos}


def env(tipo: TipoDePerfil, usuarios: dict[str, Credencial]) -> str:
    """Conteúdo do `.env` do perfil (segredo: fica em infra/twin/gerado/, fora do git)."""
    linhas = [
        "# Gerado por honeyant-twin preparar. NÃO versionar: tem as senhas da demo.",
        f"PERFIL={tipo.value}",
        f"PORTA_MQTT={PORTA[tipo]}",
    ]
    for id_, c in usuarios.items():
        linhas += [
            f"{_variavel(id_, 'USUARIO')}={c.usuario}",
            f"{_variavel(id_, 'SENHA')}={c.senha}",
        ]
    return "\n".join(linhas) + "\n"


def senhas_para_mosquitto(usuarios: dict[str, Credencial]) -> str:
    """Arquivo `usuario:senha` em texto, que o `mosquitto_passwd -U` transforma em hash."""
    return "".join(f"{c.usuario}:{c.senha}\n" for c in usuarios.values())
