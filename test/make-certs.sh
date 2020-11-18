#!/bin/bash
set -euo pipefail

# this script must be run as root
if [ $UID != 0 ]; then
  echo This script must be run as root.
  exit 1
fi

TEST_PATH=${1:-test}
TEST_DATA=${TEST_PATH}/data

CA_DIR="/etc/osbuild-composer"
echo "Generating certificates"
mkdir -p ${CA_DIR}

CONFIG="${TEST_DATA}/openssl.conf"

# The CA
echo "-=[ CA"
touch "${CA_DIR}/index.txt"
openssl req -new -nodes -x509 \
        -config "${CONFIG}" \
        -extensions osbuild_ca_ext \
        -keyout "${CA_DIR}/ca-key.pem" \
        -out "${CA_DIR}/ca-crt.pem" \
        -subj "/CN=osbuild.org"

# composer
echo "-=[ composer"
openssl genrsa -out ${CA_DIR}/composer-key.pem 2048
openssl req -new -sha256 \
        -config "${CONFIG}" \
        -key ${CA_DIR}/composer-key.pem	\
        -out ${CA_DIR}/composer-csr.pem \
        -subj "/CN=composer" \
        -addext "subjectAltName=DNS.1:localhost,DNS.2:composer"

openssl ca -config "$CONFIG" -batch \
        -extensions osbuild_server_ext \
        -in "${CA_DIR}/composer-csr.pem" \
        -out "${CA_DIR}/composer-crt.pem"

# koji
echo "-=[ koji"
openssl genrsa -out ${CA_DIR}/koji-key.pem 2048
openssl req -new -sha256 \
        -config "${CONFIG}" \
        -key ${CA_DIR}/koji-key.pem	\
        -out ${CA_DIR}/koji-csr.pem \
        -subj "/CN=localhost" \
        -addext "subjectAltName=DNS.1:localhost,DNS.2:org.osbuild.koji.koji"

openssl ca -config "$CONFIG" -batch \
        -extensions osbuild_server_ext \
        -in "${CA_DIR}/koji-csr.pem" \
        -out "${CA_DIR}/koji-crt.pem"

# client
echo "-=[ client"
openssl genrsa -out ${CA_DIR}/client-key.pem 2048
openssl req -new -sha256 \
        -config "${CONFIG}" \
        -key ${CA_DIR}/client-key.pem	\
        -out ${CA_DIR}/client-csr.pem \
        -subj "/CN=client.osbuild.local" \
        -addext "subjectAltName=DNS:client.osbuild.local"

openssl ca -config "$CONFIG" -batch \
        -extensions osbuild_client_ext \
        -in "${CA_DIR}/client-csr.pem" \
        -out "${CA_DIR}/client-crt.pem"

# fix permissions for composer
chown _osbuild-composer:_osbuild-composer ${CA_DIR}/composer-*

echo "-=[ Updating system trust chain"
cp ${CA_DIR}/ca-crt.pem \
   /etc/pki/ca-trust/source/anchors/osbuild-ca-crt.pem

update-ca-trust
