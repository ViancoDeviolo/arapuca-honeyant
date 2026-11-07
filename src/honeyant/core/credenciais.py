"""Credenciais conhecidas: o que um atacante tenta primeiro numa casa inteligente.

União de duas fontes:

1. as credenciais **completas** (usuário e senha não vazios) do resumo real da isca;
2. uma lista **estática e pequena** de credenciais padrão de fábrica de IoT.

A lista estática vem de listas públicas de credenciais padrão de IoT, as mesmas que botnets
como a Mirai usam para entrar em câmeras e roteadores. Ela existe porque a isca não garante
credenciais completas: o resumo real das últimas 24 h de 07/11/2026 tinha só 3 credenciais,
todas incompletas (usuário vazio, só usuário, ou senha vazia).

O sensor marca `credencial_vazada` quando a senha que passou em claro está nesta união; o
pathfinder soma a fraqueza (+4) a partir dessa marca.
"""

from honeyant.core.resumo import ResumoDeAmeaca

Credencial = tuple[str, str]

# Listas públicas de credenciais padrão de fábrica de IoT (usadas por botnets como a Mirai).
CREDENCIAIS_PADRAO_DE_FABRICA: frozenset[Credencial] = frozenset(
    {
        ("admin", "admin"),
        ("root", "root"),
        ("admin", "1234"),
        ("root", "12345"),
        ("admin", "password"),
    }
)

# A câmera do perfil inseguro: credencial padrão de fábrica, presente nessas listas.
CREDENCIAL_DA_CAMERA: Credencial = ("admin", "admin")


def credenciais_completas(resumo: ResumoDeAmeaca) -> frozenset[Credencial]:
    return frozenset((c.usuario, c.senha) for c in resumo.top_credenciais if c.usuario and c.senha)


def credenciais_conhecidas(resumo: ResumoDeAmeaca | None = None) -> frozenset[Credencial]:
    """Completas do resumo (se houver) ∪ padrões de fábrica."""
    if resumo is None:
        return CREDENCIAIS_PADRAO_DE_FABRICA
    return credenciais_completas(resumo) | CREDENCIAIS_PADRAO_DE_FABRICA
