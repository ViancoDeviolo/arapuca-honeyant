"""Contrato PerfilDaCasa: a casa simulada descrita como grafo dirigido.

Lido pelo twin (para subir os dispositivos), pelo sensor (para saber o que observar)
e pelo pathfinder (para calcular a rota). Não contém senhas: elas ficam no `.env` local.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from honeyant.core.comum import PADRAO_ID, chave_aresta
from honeyant.core.eventos import Servico

__all__ = ["Aresta", "No", "PerfilDaCasa", "TipoDeNo", "TipoDePerfil", "chave_aresta"]

Escala = Field(ge=0, le=10)


class TipoDePerfil(StrEnum):
    INSEGURO = "inseguro"
    SEGURO = "seguro"


class TipoDeNo(StrEnum):
    INTERNET = "internet"
    CAMERA = "camera"
    ROTEADOR = "roteador"
    LAMPADA = "lampada"
    TOMADA = "tomada"
    TERMOSTATO = "termostato"
    BROKER = "broker"
    FECHADURA = "fechadura"


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class No(_Modelo):
    """Um dispositivo (ou a internet). `x` e `y` fixam a câmara no formigueiro."""

    id: str = Field(pattern=PADRAO_ID)
    tipo: TipoDeNo
    rotulo: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    sensibilidade: int = Escala


class Aresta(_Modelo):
    """Ligação dirigida por onde um atacante pode passar de `origem` para `destino`.

    `fraqueza_fixa` só é usada nas arestas que o sensor não observa (lan, upnp e o
    telnet vindo da internet). Nas outras fica `None` e a fraqueza vem da evidência.
    """

    origem: str = Field(pattern=PADRAO_ID)
    destino: str = Field(pattern=PADRAO_ID)
    servico: Servico
    exposicao: int = Escala
    fraqueza_fixa: int | None = Field(default=None, ge=0, le=10)

    @property
    def chave(self) -> str:
        return chave_aresta(self.origem, self.destino)

    @model_validator(mode="after")
    def _sem_laco(self) -> Self:
        if self.origem == self.destino:
            raise ValueError("aresta não pode ligar um nó a ele mesmo")
        return self


class PerfilDaCasa(_Modelo):
    schema_version: Literal[1] = 1
    perfil: TipoDePerfil
    origem: Literal["internet"] = "internet"
    alvo: Literal["fechadura"] = "fechadura"
    nos: list[No] = Field(min_length=2, max_length=50)
    arestas: list[Aresta] = Field(max_length=200)

    @model_validator(mode="after")
    def _grafo_consistente(self) -> Self:
        ids = [n.id for n in self.nos]
        if len(ids) != len(set(ids)):
            raise ValueError("id de nó duplicado")
        for obrigatorio in (self.origem, self.alvo):
            if obrigatorio not in ids:
                raise ValueError(f"perfil precisa do nó {obrigatorio!r}")
        chaves = [a.chave for a in self.arestas]
        if len(chaves) != len(set(chaves)):
            raise ValueError("aresta duplicada")
        conhecidos = set(ids)
        for a in self.arestas:
            for ponta in (a.origem, a.destino):
                if ponta not in conhecidos:
                    raise ValueError(f"aresta {a.chave} cita nó inexistente {ponta!r}")
        return self

    def no(self, id_: str) -> No:
        return next(n for n in self.nos if n.id == id_)
