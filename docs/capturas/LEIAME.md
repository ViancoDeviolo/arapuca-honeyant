# Capturas antes e depois da mitigação

Prova da vulnerabilidade **real** da casa simulada e da mitigação:

| Arquivo | Perfil | O que mostra |
|---|---|---|
| [`antes.pcap`](antes.pcap) | inseguro (Mosquitto na 1883, sem TLS, sem senha, sem ACL) | `CONNECT` MQTT com **usuário e senha legíveis**. A câmera usa `admin`/`admin`, a credencial que os atacantes mais tentaram na isca |
| [`depois.pcap`](depois.pcap) | seguro (8883 com TLS, senha forte por dispositivo, ACL por tópico, câmera isolada) | Só TLS: nenhum `CONNECT` legível, nenhuma senha |

As credenciais nas capturas são **de teste, geradas para a demo**. Nenhuma senha real de
ninguém aparece aqui. As senhas do perfil seguro são aleatórias e recriadas a cada
`honeyant-twin preparar`; além disso, estão cifradas no `depois.pcap`.

## Como abrir no Wireshark

1. Abra `antes.pcap`.
2. No filtro, digite `mqtt.msgtype == 1` (só os `CONNECT`).
3. Clique num pacote e abra *MQ Telemetry Transport Protocol → Connect Command*: os campos
   **User Name** e **Password** aparecem em texto.
4. Abra `depois.pcap` com o mesmo filtro: nenhum pacote. Com `tls`, aparecem os handshakes
   (para o Wireshark decodificar a 8883 como TLS: *Analyze → Decode As… → TCP port 8883 → TLS*).

## O que as capturas de 07/11/2026 contêm

Conferido com o `tshark` (o Wireshark de linha de comando):

| | `antes.pcap` | `depois.pcap` |
|---|---|---|
| Pacotes | 422 | 485 |
| `CONNECT` MQTT legíveis (`mqtt.msgtype == 1`) | 36 | **0** |
| Handshakes TLS (Client Hello) | 0 | 27 |

Trecho do `antes.pcap` (`tshark -Y "mqtt.msgtype == 1" -T fields -e mqtt.clientid -e mqtt.username -e mqtt.passwd`):

```
camera            admin       admin
camera-comando    admin       admin
fechadura         fechadura   fechadura
lampada           lampada     lampada
```

## Como reproduzir

Com o Docker Desktop aberto, na raiz do repositório:

```bash
uv run honeyant-twin preparar     # senhas, CA e certificados de teste em infra/twin/gerado/ (fora do git)
uv run honeyant-capturar          # ~1 min: grava antes.pcap (inseguro) e depois.pcap (seguro)
```

O tcpdump roda num container que compartilha a interface do broker (`infra/twin/compose.yml`,
serviço `captura`). É o único jeito de ver o tráfego entre containers no Docker Desktop do
Windows: o Wireshark no host não enxerga essa rede.

Para conferir sem o Wireshark:

```bash
docker run --rm -v "$PWD/docs/capturas:/c:ro" --entrypoint tshark nicolaka/netshoot \
  -r /c/antes.pcap -Y "mqtt.msgtype == 1" -T fields -e mqtt.username -e mqtt.passwd
```

## Mitigação na casa simulada

```bash
uv run honeyant-twin subir           # perfil inseguro
uv run honeyant-mitigar              # troca para o seguro (TLS, senha, ACL, câmera isolada)
uv run honeyant-mitigar --desfazer   # volta ao inseguro, para repetir a demo
```

O botão "Aplicar mitigação" do painel é só visual e aponta para estas capturas.
