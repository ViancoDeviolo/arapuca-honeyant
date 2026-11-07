#!/bin/sh
# Dispositivo simulado da casa: publica o próprio estado a cada INTERVALO segundos e
# escuta o tópico de comando. Roda na imagem do Mosquitto (mosquitto_pub/sub), sem build.
# As variáveis vêm do compose gerado pela planta (honeyant-twin preparar).
set -u

conexao="-h $MQTT_HOST -p $MQTT_PORTA -u $MQTT_USUARIO -P $MQTT_SENHA"
if [ -n "${MQTT_CAFILE:-}" ]; then
  conexao="$conexao --cafile $MQTT_CAFILE"
fi

# shellcheck disable=SC2086  # a separação de $conexao em argumentos é intencional
mosquitto_sub $conexao -i "$ID-comando" -t "$TOPICO_COMANDO" \
  | while read -r comando; do echo "[$ID] comando recebido: $comando"; done &

n=0
while true; do
  # shellcheck disable=SC2086
  if mosquitto_pub $conexao -i "$ID" -t "$TOPICO_ESTADO" -m "{\"id\":\"$ID\",\"leitura\":$n}"; then
    echo "[$ID] estado $n publicado"
  else
    echo "[$ID] falha ao publicar o estado $n"
  fi
  n=$((n + 1))
  sleep "$INTERVALO"
done
