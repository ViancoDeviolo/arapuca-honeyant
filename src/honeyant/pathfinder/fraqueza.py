"""Fraqueza da aresta e frequência de ataque: funções puras (spec, seção 8)."""

from honeyant.core.eventos import Servico
from honeyant.core.evidencia import EvidenciaDeRede
from honeyant.core.resumo import ResumoDeAmeaca

PONTOS_CREDENCIAL_VAZADA = 4
PONTOS_TEXTO_PURO = 3
PONTOS_SEM_AUTENTICACAO = 2
PONTOS_SEM_ACL = 1
FRAQUEZA_MAXIMA = 10


def _risco(valor: bool | None, *, ruim_quando: bool) -> bool:
    """`None` (não observado) conta como risco: postura conservadora."""
    return valor is None or valor is ruim_quando


def fraqueza(evidencia: EvidenciaDeRede | None) -> int:
    """Pontua de 0 a 10 o quanto a aresta está desprotegida."""
    if evidencia is None:
        return FRAQUEZA_MAXIMA
    pontos = 0
    if _risco(evidencia.credencial_vazada, ruim_quando=True):
        pontos += PONTOS_CREDENCIAL_VAZADA
    if _risco(evidencia.texto_puro, ruim_quando=True):
        pontos += PONTOS_TEXTO_PURO
    if _risco(evidencia.autenticacao_exigida, ruim_quando=False):
        pontos += PONTOS_SEM_AUTENTICACAO
    if _risco(evidencia.acl_bloqueia, ruim_quando=False):
        pontos += PONTOS_SEM_ACL
    return min(pontos, FRAQUEZA_MAXIMA)


def bloqueada(evidencia: EvidenciaDeRede | None) -> bool:
    """Só bloqueia o que foi *observado* como inalcançável; na dúvida, a aresta existe."""
    return evidencia is not None and evidencia.alcancavel is False


def frequencia(resumo: ResumoDeAmeaca, servico: Servico) -> float:
    """Fração (0–1) dos ataques da janela que miraram este serviço."""
    if resumo.total_eventos == 0:
        return 0.0
    return resumo.por_servico.get(servico, 0) / resumo.total_eventos
