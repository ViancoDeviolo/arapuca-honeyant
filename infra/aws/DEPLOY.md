# Deploy da isca na EC2

Este documento descreve como colocar a isca (`arapuca`) no ar numa EC2 da AWS **sem que ela consiga iniciar conexões para fora**. Ele não traz IP, ID de conta nem nome de chave: use os seus.

Convenções: `<IP>` é o IP público da instância; `<USUARIO>` é o usuário SSH da AMI (`ubuntu` no Ubuntu, `ec2-user` no Amazon Linux); `<CHAVE>` é o arquivo `.pem`.

## 1. Antes de tudo: custo e política de uso

1. **Billing → Budgets:** orçamento de custo mensal de **US$ 10**, com alertas por e-mail em 50% e 100%.
2. **Billing → Credits:** verificar se a conta tem créditos promocionais.
3. **Política de uso:** ler a [Acceptable Use Policy da AWS](https://aws.amazon.com/aup/) e registrar a conclusão no [ADR 0004](../../docs/adr/0004-isca-baixa-interacao.md) **antes** de subir a isca.

## 2. Instância

- Tipo t3.micro, us-east-1, 12 GB de disco, 2 GB de swap (necessário para o build com 1 GB de RAM).
- Docker Engine e plugin Compose instalados (feito durante uma janela de saída, ver seção 4).

## 3. Security Group

| Direção | Porta | Origem/destino | Motivo |
|---|---|---|---|
| Entrada | TCP 23 | `0.0.0.0/0` e `::/0` | Telnet falso |
| Entrada | TCP 1883 | `0.0.0.0/0` e `::/0` | MQTT falso |
| Entrada | TCP 22 | somente "Meu IP" | administração |
| Saída | — | **nenhuma regra** | a isca nunca inicia conexões |

O Security Group é *stateful*: as respostas às conexões recebidas saem normalmente, mesmo sem regra de saída.

## 4. Janela de saída (só durante o deploy)

1. No console, adicionar ao Security Group as regras de **saída** TCP 80 e TCP 443 para `0.0.0.0/0`.
2. Fazer o deploy (seção 5).
3. **Remover as duas regras de saída** e conferir (seção 6).

Registre início e fim de cada janela na seção 4.1 (só data, hora e motivo, sem dados da conta).

## 4.1 Registro das janelas de saída da EC2

Fonte: histórico de eventos do AWS CloudTrail (us-east-1), eventos
`AuthorizeSecurityGroupEgress` e `RevokeSecurityGroupEgress` no Security Group da isca.
Horários em Brasília (UTC-03:00).

| Evento | Data e hora (BRT) | O que aconteceu |
|---|---|---|
| Saída bloqueada | 05/11 18:54:13 | Removida a regra padrão "todo o tráfego" do Security Group da isca, na criação |
| Janela 1 aberta | 05/11 19:28:09 | HTTP e HTTPS de saída liberados para a instalação inicial |
| Janela 1 fechada | 05/11 19:42:26 | Regras removidas; timeout do curl confirmado na EC2 (14 min aberta) |
| Janela 2 aberta | 05/11 22:24:40 | Primeiro deploy da isca |
| Janela 2 fechada | 05/11 22:30:00 | Regras removidas (5 min aberta) |
| Janela 3 aberta | 06/11 18:23:15 | Teste do mode=ro no SQLite e atualização do deploy |
| Janela 3 fechada | 06/11 19:10:24 | Regras removidas (47 min aberta) |
| Janela 4 aberta | 07/11 16:52:31 | Build do exportador do resumo real |
| Janela 4 fechada | 07/11 16:53:49 | Regras removidas; timeout do curl confirmado na EC2 (1 min aberta) |

**Procedimento:** a saída fica bloqueada o tempo todo; é liberada só para HTTP/HTTPS
durante instalações e deploys, fechada logo depois e conferida com
`curl -m 5 https://example.com`, que precisa dar timeout.

**Nota:** em 05/11 às 19:14:10, as regras de saída foram adicionadas por engano no Security
Group padrão da VPC, que não está associado à instância da isca. A isca não foi afetada.

**Como auditar:** CloudTrail → Histórico de eventos, filtrando pelos nomes de evento
`AuthorizeSecurityGroupEgress` e `RevokeSecurityGroupEgress`.

## 5. Deploy

```bash
ssh -i <CHAVE> <USUARIO>@<IP>

df -h /                     # precisa de pelo menos 3 GB livres
git clone https://github.com/ViancoDeviolo/arapuca-honeyant.git   # ou: cd arapuca-honeyant && git pull
cd arapuca-honeyant
git switch <branch>         # main, ou a branch em revisão
docker compose -f infra/compose.cloud.yml up -d --build
docker compose -f infra/compose.cloud.yml ps        # isca: "running"
docker compose -f infra/compose.cloud.yml logs isca | tail -5   # {"acao": "iniciada", ...}
docker image prune -f       # libera espaço dos estágios de build
```

O build baixa a base DB-IP Lite e as dependências Python; por isso precisa da janela de saída.

## 6. Verificações

1. **Saída bloqueada** (depois de fechar a janela), na instância:
   ```bash
   curl -m 5 https://example.com     # precisa FALHAR por timeout
   ```
2. **Isca respondendo**, do seu PC (PowerShell):
   ```powershell
   Test-NetConnection <IP> -Port 23      # TcpTestSucceeded : True
   Test-NetConnection <IP> -Port 1883    # TcpTestSucceeded : True
   ```
3. **Eventos chegando** (alguns minutos depois), na instância:
   ```bash
   docker compose -f infra/compose.cloud.yml exec isca honeyant-isca estatisticas
   # {"total": N, "acumulado": {"telnet": ..., "mqtt": ...}} com N > 0
   ```

## 7. Verificação do mode=ro

O spec (seção 3) pede que quem lê o banco da isca, o painel e o intel, fique em outro container, com **duas camadas** contra escrita: a conexão SQLite em `mode=ro` e um usuário sem permissão de escrita no arquivo do banco. O container `verificar-ro` (usuário `10002`, grupo `10001` da isca) checa as duas camadas e sai com 0 só se ambas seguram.

Na instância, com a isca no ar:

```bash
docker compose -f infra/compose.cloud.yml build isca          # troca a imagem; não recria a isca
docker compose -f infra/compose.cloud.yml up -d init-dados    # diretório /dados 2775
docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml run --rm verificar-ro
```

Esperado: `"escrita_bloqueada": true` (camada mode=ro), `"arquivo_gravavel": false` (camada do usuário) e saída 0.

**Resultado em 06/11/2026 (EC2, isca no ar desde 05/11):**

```json
{"modo": "ro", "eventos": 200, "acumulado": {"telnet": 198, "mqtt": 2}, "escrita_bloqueada": true, "arquivo_gravavel": false}
```

**Conclusão:** a leitura em `mode=ro` funciona com o compose real. O plano B (endpoint interno da isca) não é necessário.

O mesmo teste também passou no Docker Desktop do notebook, em dois cenários:
- com a isca no ar;
- com a isca parada, quando o desligamento limpo apaga o `-wal`/`-shm`. Graças ao diretório 2775, o leitor os recria, e a isca retoma os arquivos ao voltar.

**Cuidado para o painel:** um leitor de longa duração que esteja com o `-shm` aberto *enquanto a isca liga* não foi testado. Ao integrar o painel, repita este teste reiniciando a isca com o painel no ar.

## 7.1 Exportar o resumo real

O painel e o twin usam o `docs/demo/resumo-real-<AAAA-MM-DD>.json` mais recente (a senha
da câmera no perfil inseguro é a mais tentada dele). O resumo **não tem IP**: só contagens,
as credenciais mais tentadas e a intenção.

Na instância, com o código atualizado (`git fetch && git checkout <branch>`) e a janela de
saída aberta **só durante o build** (seção 4):

```bash
docker compose -f infra/compose.cloud.yml build isca
docker compose -f infra/compose.cloud.yml -f infra/compose.verificar-ro.yml \
  run --rm -T --entrypoint honeyant-exportar-resumo verificar-ro > resumo-real.json
```

No notebook:

```bash
scp -i <chave>.pem ubuntu@<ip-da-ec2>:~/arapuca-honeyant/resumo-real.json \
  docs/demo/resumo-real-$(date +%F).json
grep -cE '([0-9]{1,3}\.){3}[0-9]{1,3}' docs/demo/resumo-real-*.json   # precisa dar 0
uv run pytest tests/e2e/test_resumo_real.py   # se a rota mudar, pare e avise antes de calibrar
uv run honeyant-gravar-replay                 # o resumo em uso mudou
```

**Nenhum IPv4 no resumo:** o intel troca qualquer IPv4 dentro de usuário e senha por
`<ipv4>` antes de exportar, e o teste `test_nenhum_ipv4_nos_resumos_versionados` falha se
algum `docs/demo/resumo-*.json` tiver algo com cara de IPv4. O `grep` acima precisa dar `0`
em cada arquivo antes do commit.

## 8. Acompanhamento e encerramento

- No dia seguinte ao deploy, em **Billing → Cost Explorer**, confirmar que o gasto diário está dentro do previsto (R$ 20–50 até a apresentação), incluindo o IPv4 público.
- **Depois da ExpoTech (28/11/2026):** parar ou encerrar a instância e liberar o IP.
