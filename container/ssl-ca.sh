#!/bin/bash
set -eux

HOME=pki/koji
CONF=ssl.cnf

# prepare the directories
mkdir -p ${HOME}/{certs,private,confs}

touch "$HOME/index.txt"
echo 01 > "$HOME/serial"


# private key
openssl genrsa -out "$HOME/private/koji_ca_cert.key" 2048

# CA
openssl req -config $CONF \
	-new -x509 \
	-subj "/C=DE/ST=BE/L=BE/O=RH/CN=koji" \
	-days 3650 \
	-key "${HOME}/private/koji_ca_cert.key" \
	-out "${HOME}/koji_ca_cert.crt" \
	-extensions v3_ca

#
openssl genrsa -out "${HOME}/private/kojihub.key" 2048

openssl req -new -sha256 \
	-config $CONF \
	-key "${HOME}/private/kojihub.key" \
	-out "${HOME}/certs/kojihub.csr" \
	-subj "/C=DE/ST=BE/L=BE/O=RH/CN=localhost"

openssl x509 -req \
	-sha256 \
	-in "${HOME}/certs/kojihub.csr" \
	-CA "$HOME/koji_ca_cert.crt" \
	-CAkey "$HOME/private/koji_ca_cert.key" \
	-CAcreateserial \
	-out "${HOME}/certs/kojihub.crt"

