#!/usr/bin/bash
set -eux

shutdown () {
    EXIT_CODE=$?

    echo "Shutting down containers, please wait..."

    podman stop koji.db || true
    podman stop koji.hub || true
    podman pod rm -f koji || true

    exit $EXIT_CODE
}

trap shutdown EXIT

mkdir -p mnt/koji

podman pod create --name koji -p 5432 -p 8080:80 -p 8081:443

podman run -d --rm \
       --env-file container/env \
       --pod koji \
       --name koji.db \
       postgres:12-alpine

podman run -it --rm \
       --env-file container/env \
       --pod koji \
       -v $(pwd)/container/pki/koji:/etc/pki/koji:Z \
       -v $(pwd)/mnt:/mnt:Z \
       --name koji.hub \
       koji-server

echo "Running, press CTRL+C to stop..."
sleep infinity
