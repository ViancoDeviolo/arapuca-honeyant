#!/bin/sh
# Baixa as bases offline DB-IP Lite (país e ASN), licença CC-BY 4.0.
# Atribuição: "IP Geolocation by DB-IP (https://db-ip.com)".
# Uso: baixar-dbip.sh <diretorio-destino>
set -eu

destino="${1:-/geo}"
mkdir -p "$destino"

baixar() {
    nome="$1"   # country | asn
    for mes in "$(date +%Y-%m)" "$(date -d "$(date +%Y-%m-01) -1 month" +%Y-%m)"; do
        url="https://download.db-ip.com/free/dbip-${nome}-lite-${mes}.mmdb.gz"
        if curl -fsSL --retry 3 -o "$destino/${nome}.mmdb.gz" "$url"; then
            gunzip -f "$destino/${nome}.mmdb.gz"
            mv "$destino/${nome}.mmdb" "$destino/dbip-${nome}-lite.mmdb"
            echo "ok: $url"
            return 0
        fi
        echo "indisponível: $url" >&2
    done
    return 1
}

baixar country
baixar asn
