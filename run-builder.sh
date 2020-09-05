#!/usr/bin/bash

SHARE_DIR=/tmp/osbuild-composer-koji-test
DATA_DIR=/var/tmp/osbuild-koji-data

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

# decide whether podman or docker should be used
if which podman 2>/dev/null >&2; then
  CONTAINER_RUNTIME=podman
elif which docker 2>/dev/null >&2; then
  CONTAINER_RUNTIME=docker
else
  echo No container runtime found, install podman or docker.
  exit 2
fi

${CONTAINER_RUNTIME} run --rm -i -t --name org.osbuild.koji.builder --network org.osbuild.koji \
  -v "${SHARE_DIR}:/share:z" \
  -v "${DATA_DIR}:/mnt:z" \
  --hostname org.osbuild.koji.kojid \
  --add-host=composer:$(ip route show dev cni-podman0 | cut -d\  -f7) \
  koji.builder
