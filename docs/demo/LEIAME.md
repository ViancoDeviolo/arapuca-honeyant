# Dados da demonstração

| Arquivo | O que é |
|---|---|
| `perfil-inseguro.json`, `perfil-seguro.json` | A casa antes e depois da mitigação |
| `evidencias-inseguro.json`, `evidencias-seguro.json` | Evidências de rede usadas pelo pathfinder |
| `resumo-congelado.json` | Resumo **de exemplo** (usado quando não há resumo real) |
| `resumo-real-AAAA-MM-DD.json` | Resumo **real** da isca, exportado na EC2 (`infra/aws/DEPLOY.md`, seção 7.1). Sem IPs |
| `replay-*.jsonl` | Snapshots do ACO gravados com a semente 42 (plano B offline) |

## `MGLNDD_<ipv4>_<porta>` nas credenciais

No resumo real aparece um usuário no formato `MGLNDD_<ipv4>_23`. É a assinatura de um
**scanner automatizado** que varre a internet e manda, como "usuário", o IP e a porta do
alvo que ele acabou de encontrar. O IP ecoado é o da **própria isca**, não o de um
atacante. Mesmo assim, nenhum IPv4 entra no repositório: o intel troca qualquer IPv4
dentro de usuário e senha por `<ipv4>` antes de exportar. É uma boa evidência de que parte
do tráfego que a isca recebe é varredura automática, não alguém tentando entrar de fato.

## Credenciais conhecidas e a senha da câmera

A câmera do perfil inseguro usa `admin`/`admin`: **credencial padrão de fábrica, presente
nas listas públicas usadas por botnets de IoT**. O sensor marca uma credencial como vazada
quando ela é **conhecida**, isto é, está na união de:

1. as credenciais completas (usuário e senha não vazios) do resumo real da isca;
2. uma lista estática e pequena de credenciais padrão de fábrica de IoT
   (`src/honeyant/core/credenciais.py`): `admin/admin`, `root/root`, `admin/1234`,
   `root/12345` e `admin/password`.

A lista estática existe porque a isca não garante credenciais completas. O resumo real das
últimas 24 h de 07/11/2026 tinha 164 eventos, mas só 3 credenciais, todas incompletas: um
usuário vazio, o `MGLNDD_<ipv4>_23` sem senha e `root` com senha vazia.
