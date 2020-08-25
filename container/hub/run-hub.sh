#!/bin/bash
set -eux

sed -i -e "s|LogLevel warn|LogLevel debug|" /etc/httpd/conf/httpd.conf

tee -a /etc/httpd/conf.d/kojihub.conf <<END
<Location /kojihub/ssllogin>
         SSLVerifyClient require
         SSLVerifyDepth  10
         SSLOptions +StdEnvVars
</Location>
END

sed -i  -e "s|^SSLCertificateFile.*|SSLCertificateFile /etc/pki/koji/certs/kojihub.crt|" \
        -e "s|^SSLCertificateKeyFile.*|SSLCertificateKeyFile /etc/pki/koji/private/kojihub.key|" \
        -e "s|^#SSLCertificateChainFile.*|SSLCertificateChainFile /etc/pki/koji/koji_ca_cert.crt|" \
        -e "s|^#SSLCACertificateFile.*|SSLCACertificateFile /etc/pki/koji/koji_ca_cert.crt|" \
	-e "s|^#SSLVerifyDepth.*|SSLVerifyDepth 1|" \
        -e "s|LogLevel warn|LogLevel debug|" \
        -e "s|^#ServerName.*|ServerName localhost|" \
        /etc/httpd/conf.d/ssl.conf

sed -i  -e "s|^#ServerName.*|ServerName localhost|" \
        /etc/httpd/conf/httpd.conf

# wait for postgres to come on-line
timeout 10 bash -c "until printf '' 2>/dev/null >/dev/tcp/${POSTGRES_HOST}/5432; do sleep 0.1; done"

# psql uses PGPASSWORD env variable
export PGPASSWORD="${POSTGRES_PASSWORD}"

# create an "alias" for the long psql command
psql_cmd() {
  psql -h "${POSTGRES_HOST}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" "$@"
}

# initialize the database if it isn't initialized already
if ! psql_cmd -c "select * from users" &>/dev/null; then
    psql_cmd -f /usr/share/doc/koji/docs/schema.sql >/dev/null

    psql_cmd -c "insert into users (name, password, status, usertype) values ('kojiadmin', 'kojipass', 0, 0)" >/dev/null
    psql_cmd -c "insert into user_perms (user_id, perm_id, creator_id) values (1, 1, 1)" >/dev/null
    psql_cmd -c "insert into users (name, password, status, usertype) values ('osbuild', 'osbuildpass', 0, 0)" >/dev/null

    # create content generator osbuild, give osbuild users access to it
    psql_cmd -c "insert into content_generator (name) values ('osbuild')" >/dev/null
    psql_cmd -c "insert into cg_users (cg_id, user_id, creator_id, active) values (1, 2, 1, true)" >/dev/null
fi

mkdir -p /mnt/koji/{packages,repos,work,scratch,repos-dist}

# run apache
httpd -DFOREGROUND
