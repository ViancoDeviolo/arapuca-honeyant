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

Anote início e fim de cada janela em `infra/aws/janelas.md` (fora do Git, se tiver dados da conta).

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

## 7. Acompanhamento e encerramento

- No dia seguinte ao deploy, em **Billing → Cost Explorer**, confirmar que o gasto diário está dentro do previsto (R$ 20–50 até a apresentação), incluindo o IPv4 público.
- **Depois da ExpoTech (28/11/2026):** parar ou encerrar a instância e liberar o IP.
