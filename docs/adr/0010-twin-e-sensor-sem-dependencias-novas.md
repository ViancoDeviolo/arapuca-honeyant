# ADR 0010 — Twin e sensor sem dependências novas

- **Status:** aceito
- **Data:** 2026-11-07

## Contexto

A vulnerabilidade precisa ser **real** e **identificada**: uma casa simulada com MQTT de
verdade, capturas antes e depois da mitigação, e um sensor que encontre o problema no
tráfego. O prazo era de horas, e cada dependência nova é mais um ponto de falha no
notebook da apresentação (imagens Python para construir, versões, cache do Docker).

## Decisão

- **Twin:** os 5 dispositivos rodam `mosquitto_pub` e `mosquitto_sub` na **mesma imagem
  fixada do Mosquitto** (`infra/twin/dispositivo.sh`), em vez de um cliente `paho-mqtt` numa
  imagem Python. Quais dispositivos sobem e em quais tópicos falam sai da
  `planejar_dispositivos` (`twin/planta.py`).
- **Certificados:** CA e certificado do broker gerados com `openssl` na imagem `netshoot`
  (já fixada para a captura). A chave da CA é apagada depois de assinar.
- **Sensor:** leitor de `.pcap` e parser do `CONNECT` MQTT **próprios** (`sensor/adapters/pcap.py`,
  `sensor/mqtt.py`), em vez de Scapy. Formatos suportados: Ethernet, SLL e SLL2 (o do
  `tcpdump -i any`), IPv4 e IPv6.
- **Fuzzy de intenção** do intel em Python puro, porque roda na imagem da isca, que não
  leva numpy nem scikit-fuzzy.

## Alternativas consideradas

- **paho-mqtt:** cliente mais realista (conexão persistente), mas uma imagem Python a mais
  para construir e manter. Descartado para o MVP.
- **Scapy:** lê de tudo, mas é grande, e o sensor só precisa de um tipo de pacote.
  Descartado.

## Consequências

- Os dispositivos reconectam a cada publicação (um `CONNECT` a cada 3 s). Não é realista,
  mas deixa a credencial visível no `antes.pcap` muitas vezes.
- O parser não remonta fluxos TCP: um `CONNECT` partido em dois segmentos não é visto
  (não acontece com os clientes da demo).
- Ler uma interface ao vivo é escrever outro adaptador de `FonteDeTrafego`.
