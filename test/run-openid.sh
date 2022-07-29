#!/bin/bash
set -eu

SERVER_PORT="8081"
PIDFILE="/run/composer-openid-server.pid"

server_start() {
  echo "Starting mock OpenID server at :${SERVER_PORT}"

  /usr/libexec/osbuild-composer-test/osbuild-mock-openid-provider \
  -rsaPubPem /etc/osbuild-composer/client-crt.pem \
  -rsaPem /etc/osbuild-composer/client-key.pem \
  -cert /etc/osbuild-composer/composer-crt.pem \
  -key /etc/osbuild-composer/composer-key.pem \
  -a ":${SERVER_PORT}" \
  -expires 10 &

  until curl --data "grant_type=refresh_token" --output /dev/null --silent --fail "https://localhost:${SERVER_PORT}/token"; do
    sleep 0.5
  done

  PID="$!"
  echo "${PID}" > "${PIDFILE}"
  echo "OpenID server running (${PID})"
}

server_stop() {
  echo "Stopping mock OpenID server"

  PID=$(cat "${PIDFILE}" 2> /dev/null || true)

  if [ -z "$PID" ]; then
     echo "Server not running!"
     return
  fi

  echo "${PID}"

  EXIT_CODE=0
  kill "${PID}" > /dev/null || EXIT_CODE=$?

  if [ "${EXIT_CODE}" != 0 ]; then
    "Could not kill process ${PID}"
  fi
}

if [  $# -lt 1 ]; then
  echo -e "Usage: $0 <start|stop>"
elif [ $1 == "start" ]; then
  server_start
elif [ $1 == "stop" ]; then
  server_stop
fi

