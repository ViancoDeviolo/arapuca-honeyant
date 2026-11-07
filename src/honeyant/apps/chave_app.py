"""`honeyant-chave-app`: gera a chave de acesso do resumo-api e o hash dela.

    uv run honeyant-chave-app

- A **chave** vai para cada pessoa que usa o app, por fora (WhatsApp). Nunca no repositório.
- A linha `HONEYANT_RESUMO_CHAVE_HASH=...` vai para `infra/resumo-api.env` na EC2 (dono
  10002, permissão 600). A EC2 guarda só o hash.
"""

import secrets

from honeyant.intel.acesso import gerar_hash


def main() -> None:
    chave = secrets.token_urlsafe(32)
    print(f"Chave de acesso (entregue a cada pessoa por fora): {chave}")
    print()
    print("Linha para infra/resumo-api.env na EC2:")
    # Entre aspas simples: o Docker Compose interpreta "$" no env_file e corromperia o hash.
    print(f"HONEYANT_RESUMO_CHAVE_HASH='{gerar_hash(chave)}'")


if __name__ == "__main__":
    main()
