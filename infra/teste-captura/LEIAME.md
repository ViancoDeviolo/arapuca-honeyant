# Teste de viabilidade da captura MQTT

Pergunta: o `tcpdump` num container consegue gravar o tráfego MQTT da rede Docker
para ser aberto no Wireshark do Windows?

**Resposta: sim, nos dois modos (arquivo e ao vivo).** Testado em 06/11/2026.

## Como rodar

Gravando um `.pcap`:

```bash
docker compose -f infra/teste-captura/compose.yml up -d mosquitto captura
docker compose -f infra/teste-captura/compose.yml run --rm cliente
docker compose -f infra/teste-captura/compose.yml down
```

O arquivo fica em `infra/teste-captura/capturas/teste.pcap`, fora do git. No
Wireshark, o filtro `mqtt.conflags` mostra o **Connect Command** com
`User Name: camera` e `Password: 123456`.

Ao vivo (Git Bash, não PowerShell), com o compose de pé:

```bash
docker compose -f infra/teste-captura/compose.yml exec -T captura \
  tcpdump -i any -U -w - port 1883 | "/c/Program Files/Wireshark/Wireshark.exe" -k -i -
```

Em outro terminal, rode o `cliente` (comando `run --rm cliente` acima).

## Resultado

| Modo | Resultado |
|---|---|
| Arquivo `.pcap` | Connect com `camera` / `123456`, Connect Ack, Publish `casa/teste` ("oi"), Disconnect |
| Ao vivo (pipe para o Wireshark) | Os mesmos quatro pacotes chegaram em tempo real |

Ambiente: Windows 11, Docker Desktop (engine 29.8.0, Compose 5.5.1),
Wireshark/TShark 4.6.9.

## Observações

- **Não use a tag `eclipse-mosquitto:2`**: a imagem publicada em 05/11/2026 está
  quebrada (`/docker-entrypoint.sh` com 0 bytes, que dá `exec format error`, e o
  binário sem os símbolos do OpenSSL). Por isso o compose fixa a `2.0.20` por digest.
- O `.pcap` gerado aqui só tem credencial falsa, mas não é captura oficial, por
  isso fica fora do git.
- O `tcpdump` compartilha a rede do broker (`network_mode: "service:mosquitto"`),
  então nenhuma porta é publicada no host.
