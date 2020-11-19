#!/bin/bash
set -euo pipefail

TEST_PATH=${1:-test}

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

source /etc/os-release

podman build \
       --build-arg version=${VERSION_ID} \
       -t koji.hub \
       -f ${TEST_PATH}/container/hub/Dockerfile.${ID} $TEST_PATH

podman build \
       --build-arg version=${VERSION_ID} \
       -t koji.builder \
       -f ${TEST_PATH}/container/builder/Dockerfile.${ID} $TEST_PATH
