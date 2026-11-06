"""Composition root da isca: monta repositório, geo, limitador e serviços falsos.

Uso:
    honeyant-isca servir        # padrão
    honeyant-isca estatisticas  # total e acumulado por serviço, sem IPs
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import signal
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from honeyant.arapuca.adapters.geo import GeoDbIp, GeoNulo
from honeyant.arapuca.adapters.sqlite import RepositorioSqlite
from honeyant.arapuca.limites import Limitador
from honeyant.arapuca.mqtt import ServicoMqtt
from honeyant.arapuca.ports import ResolvedorGeo
from honeyant.arapuca.servidor import ServidorDaIsca
from honeyant.arapuca.telnet import ServicoTelnet

log = logging.getLogger("honeyant.isca")

ARQUIVO_PAIS = "dbip-country-lite.mmdb"
ARQUIVO_ASN = "dbip-asn-lite.mmdb"


@dataclass(frozen=True)
class ConfigIsca:
    db: Path
    geo_dir: Path
    porta_telnet: int
    porta_mqtt: int

    @classmethod
    def do_ambiente(cls, env: Mapping[str, str]) -> "ConfigIsca":
        return cls(
            db=Path(env.get("HONEYANT_DB", "/dados/isca.db")),
            geo_dir=Path(env.get("HONEYANT_GEO_DIR", "/geo")),
            porta_telnet=int(env.get("HONEYANT_PORTA_TELNET", "2323")),
            porta_mqtt=int(env.get("HONEYANT_PORTA_MQTT", "18830")),
        )


def montar_geo(geo_dir: Path) -> ResolvedorGeo:
    pais, asn = geo_dir / ARQUIVO_PAIS, geo_dir / ARQUIVO_ASN
    if pais.exists() and asn.exists():
        return GeoDbIp(pais, asn)
    log.warning("base DB-IP não encontrada em %s; país e ASN ficarão vazios", geo_dir)
    return GeoNulo()


async def servir(config: ConfigIsca) -> None:
    servidor = ServidorDaIsca(
        {config.porta_telnet: ServicoTelnet(), config.porta_mqtt: ServicoMqtt()},
        RepositorioSqlite(config.db),
        montar_geo(config.geo_dir),
        Limitador(),
    )
    portas = await servidor.iniciar()
    log.info(json.dumps({"acao": "iniciada", "portas": sorted(portas.values())}))
    parar = asyncio.Event()
    with contextlib.suppress(NotImplementedError):  # sinais não existem no Windows
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, parar.set)
    limites = asyncio.create_task(servidor.ciclo_de_limites())
    try:
        await parar.wait()
    finally:
        limites.cancel()
        await servidor.parar()
        log.info(json.dumps({"acao": "encerrada"}))


def estatisticas(config: ConfigIsca) -> dict:
    repo = RepositorioSqlite(config.db)
    acumulado = {s.value: n for s, n in repo.acumulado_por_servico().items()}
    return {"total": repo.contar(), "acumulado": acumulado}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="honeyant-isca")
    parser.add_argument("comando", nargs="?", default="servir", choices=["servir", "estatisticas"])
    args = parser.parse_args(argv)
    config = ConfigIsca.do_ambiente(os.environ)
    if args.comando == "estatisticas":
        print(json.dumps(estatisticas(config)))
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(servir(config))
