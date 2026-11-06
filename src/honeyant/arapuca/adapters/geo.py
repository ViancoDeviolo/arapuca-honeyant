"""Geolocalização offline (DB-IP Lite, CC-BY 4.0). A isca não tem saída de rede."""

from pathlib import Path

import maxminddb


class GeoNulo:
    """Usado quando a base não está disponível."""

    def resolver(self, ip: str) -> tuple[str | None, int | None]:
        return None, None


class GeoDbIp:
    def __init__(self, caminho_pais: Path, caminho_asn: Path) -> None:
        self._pais = maxminddb.open_database(str(caminho_pais))
        self._asn = maxminddb.open_database(str(caminho_asn))

    def resolver(self, ip: str) -> tuple[str | None, int | None]:
        return self._ler_pais(ip), self._ler_asn(ip)

    def _ler_pais(self, ip: str) -> str | None:
        try:
            registro = self._pais.get(ip) or {}
            return registro.get("country", {}).get("iso_code")
        except (ValueError, TypeError, AttributeError):
            return None

    def _ler_asn(self, ip: str) -> int | None:
        try:
            registro = self._asn.get(ip) or {}
            return registro.get("autonomous_system_number")
        except (ValueError, TypeError, AttributeError):
            return None
