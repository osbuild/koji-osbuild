#!/bin/bash
set -euo pipefail

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

TEST_PATH=${1:-test}
TEST_DATA=${TEST_PATH}/data
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

echo "koji" > /etc/osbuild-worker/oauth-secret

# if AWS credentials are defined in the ENV, add them to the worker's configuration
# This is needed to test the upload to the cloud
V2_AWS_ACCESS_KEY_ID="${V2_AWS_ACCESS_KEY_ID:-}"
V2_AWS_SECRET_ACCESS_KEY="${V2_AWS_SECRET_ACCESS_KEY:-}"
if [[ -n "$V2_AWS_ACCESS_KEY_ID" && -n "$V2_AWS_SECRET_ACCESS_KEY" ]]; then
   echo "Adding AWS credentials to the worker's configuration"
   sudo tee /etc/osbuild-worker/aws-credentials.toml > /dev/null << EOF
[default]
aws_access_key_id = "$V2_AWS_ACCESS_KEY_ID"
aws_secret_access_key = "$V2_AWS_SECRET_ACCESS_KEY"
EOF
   sudo tee -a /etc/osbuild-worker/osbuild-worker.toml > /dev/null << EOF

[aws]
credentials = "/etc/osbuild-worker/aws-credentials.toml"
bucket = "${AWS_BUCKET}"
EOF
fi

echo "Copying system kerberos configuration"
cp ${TEST_DATA}/krb5.local.conf \
   /etc/krb5.conf.d/local
