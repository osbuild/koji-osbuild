#!/bin/bash
set -eux

USER=$1
PASS="pass"
CONF=ssl.cnf
CACERT="koji_ca_cert.crt"
CAKEY="koji_ca_cert.key"

SSLHOME=pki/koji

openssl genrsa -out ${SSLHOME}/private/${USER}.key 2048

openssl req \
	-config ${CONF} \
	-new -nodes \
	-out ${SSLHOME}/certs/${USER}.csr \
	-key ${SSLHOME}/private/${USER}.key \
        -subj "/C=DE/ST=BE/L=BE/O=RH/CN=${USER}/emailAddress=${USER}@kojihub.local"

openssl ca \
	-config ${CONF} \
	-batch \
	-keyfile ${SSLHOME}/private/${CAKEY} \
	-cert ${SSLHOME}/${CACERT} \
	-out ${SSLHOME}/certs/${USER}.crt \
	-outdir ${SSLHOME}/certs \
	-infiles ${SSLHOME}/certs/${USER}.csr

cat ${SSLHOME}/certs/${USER}.crt ${SSLHOME}/private/${USER}.key > ${SSLHOME}/certs/${USER}.pem

CLIHOME=ssl/${USER}
rm -rf ${CLIHOME}
mkdir -p ${CLIHOME}

cp ${SSLHOME}/certs/${USER}.crt ${CLIHOME}/client.crt
cp ${SSLHOME}/certs/${USER}.pem ${CLIHOME}/client.pem
cp ${SSLHOME}/${CACERT} ${CLIHOME}/clientca.crt
cp ${SSLHOME}/${CACERT} ${CLIHOME}/serverca.crt

