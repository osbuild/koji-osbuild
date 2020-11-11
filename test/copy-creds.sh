#!/bin/bash
set -euo pipefail

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

TEST_DATA=${TEST_DATA:-test/data}
SHARE_DIR=${SHARE_DIR:-/tmp/osbuild-composer-koji-test}

mkdir -p "${SHARE_DIR}"

mkdir -p /etc/osbuild-composer
mkdir -p /etc/osbuild-worker

echo "Copying kerberos keytabs"
cp ${SHARE_DIR}/client.keytab \
   /etc/osbuild-composer/client.keytab

cp ${SHARE_DIR}/client.keytab \
   /etc/osbuild-worker/client.keytab

echo "Copying composer kerberos configuration"
cp ${TEST_DATA}/osbuild-composer.toml \
   /etc/osbuild-composer/

mkdir -p /etc/osbuild-worker
cp ${TEST_DATA}/osbuild-worker.toml \
   /etc/osbuild-worker/

echo "Copying system kerberos configuration"
cp ${TEST_DATA}/krb5.local.conf \
   /etc/krb5.conf.d/local
