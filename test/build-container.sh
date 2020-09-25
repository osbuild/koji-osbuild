#!/bin/bash
set -euo pipefail

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

source /etc/os-release

podman build \
       -t koji.hub \
       -f container/hub/Dockerfile.${ID} .

podman build -t \
       koji.builder \
       -f container/builder/Dockerfile.${ID} .
