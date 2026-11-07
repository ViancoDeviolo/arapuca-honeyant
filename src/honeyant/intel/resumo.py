"""Agregação dos eventos da isca num `ResumoDeAmeaca` (o que sai da EC2).

O evento tem o IP do atacante (dado pessoal). O resumo não: ele só tem contagens por
serviço, país e ASN, as credenciais mais tentadas e a intenção. O IP é usado apenas em
memória, para agrupar as sessões de uma mesma origem no fuzzy de intenção.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from honeyant.core.eventos import EventoDeAtaque, Servico
from honeyant.core.resumo import LIMITE_TOP_CREDENCIAIS, CredencialTentada, ResumoDeAmeaca
from honeyant.intel.anonimizar import mascarar_ipv4
from honeyant.intel.intencao import classificar

PAIS_DESCONHECIDO = "ZZ"
ASN_DESCONHECIDO = 0


def _intencoes(eventos: list[EventoDeAtaque], janela_horas: int) -> Counter:
    por_origem: dict[str, list[EventoDeAtaque]] = defaultdict(list)
    for e in eventos:
        por_origem[str(e.ip_origem)].append(e)
    contagem: Counter = Counter()
    for sessoes in por_origem.values():
        diversidade = len({(e.usuario, e.senha) for e in sessoes if e.usuario or e.senha})
        comandos = sum(len(e.comandos) for e in sessoes) / len(sessoes)
        taxa = len(sessoes) / janela_horas
        contagem[classificar(diversidade, comandos, taxa)] += len(sessoes)
    return contagem


def _mascarar(texto: str | None) -> str | None:
    return mascarar_ipv4(texto) if texto else texto


def agregar(
    eventos: Iterable[EventoDeAtaque],
    acumulado: Mapping[Servico, int],
    agora: datetime,
    janela_horas: int = 24,
) -> ResumoDeAmeaca:
    inicio = agora - timedelta(hours=janela_horas)
    na_janela = [e for e in eventos if inicio < e.ts <= agora]

    # Só sessões que mandaram algum texto: usuário ou senha vazios não são credencial.
    # IPv4 dentro do texto (scanner que ecoa o alvo) vira "<ipv4>" antes de contar.
    credenciais = Counter(
        (_mascarar(e.usuario), _mascarar(e.senha)) for e in na_janela if e.usuario or e.senha
    )
    # Mais tentadas primeiro; empate por (usuario, senha) crescente, para ser determinístico.
    top = sorted(credenciais.items(), key=lambda par: (-par[1], par[0][0] or "", par[0][1] or ""))
    return ResumoDeAmeaca(
        gerado_em=agora,
        janela_horas=janela_horas,
        total_eventos=len(na_janela),
        por_servico=dict(Counter(e.servico for e in na_janela)),
        acumulado_por_servico=dict(acumulado),
        por_pais=dict(Counter(e.pais or PAIS_DESCONHECIDO for e in na_janela)),
        por_asn=dict(Counter(e.asn if e.asn is not None else ASN_DESCONHECIDO for e in na_janela)),
        intencao=dict(_intencoes(na_janela, janela_horas)),
        top_credenciais=[
            CredencialTentada(usuario=u, senha=s, tentativas=n)
            for (u, s), n in top[:LIMITE_TOP_CREDENCIAIS]
        ],
    )
