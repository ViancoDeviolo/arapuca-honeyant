"""Um stream ativo por cliente: o mais novo vence (spec, seção 3.4)."""

import asyncio


class RegistroDeStreams:
    """Guarda o sinal de parada do stream atual de cada cliente.

    Abrir um stream novo marca o sinal do anterior do mesmo cliente, que emite `fim` e
    para. Não recusa o segundo: o navegador abre o novo antes de o servidor perceber que
    o antigo foi fechado.
    """

    def __init__(self) -> None:
        self._ativos: dict[str, asyncio.Event] = {}

    def abrir(self, cliente: str) -> asyncio.Event:
        anterior = self._ativos.get(cliente)
        if anterior is not None:
            anterior.set()
        novo = asyncio.Event()
        self._ativos[cliente] = novo
        return novo

    def fechar(self, cliente: str, evento: asyncio.Event) -> None:
        # Só remove se ainda for o atual: fechar o antigo não pode derrubar o novo.
        if self._ativos.get(cliente) is evento:
            del self._ativos[cliente]
