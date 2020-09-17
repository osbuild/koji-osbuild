#!/bin/bash
set -euo pipefail

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

TEST_DATA=${TEST_DATA:-test/data}

CA_DIR="/etc/osbuild-composer"
echo "Generating certificates"
mkdir -p ${CA_DIR}

# The CA
openssl req -new -nodes -x509 -days 365 \
        -keyout "${CA_DIR}/ca-key.pem" \
        -out "${CA_DIR}/ca-crt.pem" \
        -subj "/CN=osbuild.org"
openssl genrsa -out "${CA_DIR}/key.pem" 2048

# composer
openssl genrsa -out ${CA_DIR}/composer-key.pem 2048
openssl req -new -sha256 \
        -key ${CA_DIR}/composer-key.pem	\
        -out ${CA_DIR}/composer-csr.pem \
        -config ${TEST_DATA}/composer.ssl.conf
openssl x509 -req \
        -in ${CA_DIR}/composer-csr.pem \
        -CA ${CA_DIR}/ca-crt.pem \
        -CAkey ${CA_DIR}/ca-key.pem \
        -CAcreateserial \
        -out ${CA_DIR}/composer-crt.pem \
        -extfile ${TEST_DATA}/composer.ssl.conf \
        -extensions v3_req

# worker
openssl genrsa -out ${CA_DIR}/worker-key.pem 2048
openssl req -new -sha256 \
        -key ${CA_DIR}/worker-key.pem	\
        -out ${CA_DIR}/worker-csr.pem \
        -subj "/CN=localhost"

openssl x509 -req \
        -in ${CA_DIR}/worker-csr.pem \
        -CA ${CA_DIR}/ca-crt.pem \
        -CAkey ${CA_DIR}/ca-key.pem \
        -CAcreateserial \
        -out ${CA_DIR}/worker-crt.pem

# fix permissions for composer
chown _osbuild-composer:_osbuild-composer ${CA_DIR}/composer-*
