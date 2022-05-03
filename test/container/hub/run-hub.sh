#!/bin/bash
set -eux

if ls /share/rpms/*.rpm 1> /dev/null 2>&1; then
   echo "Using RPMs"
   rpm -i /share/rpms/koji-osbuild-?-1.*.rpm \
          /share/rpms/koji-osbuild-hub-*.rpm
else
  echo "Using local plugin"
  mkdir -p /usr/lib/koji-hub-plugins/
  cp /share/plugins/hub/osbuild.py /usr/lib/koji-hub-plugins/
fi

# Set DB credentials
sed -i  -e "s/.*DBHost =.*/DBHost = ${POSTGRES_HOST}/" \
        -e "s/.*DBUser =.*/DBUser = ${POSTGRES_USER}/" \
        -e "s/.*DBPass =.*/DBPass = ${POSTGRES_PASSWORD}/" \
        -e "s/.*DBName =.*/DBName = ${POSTGRES_DB}/" \
        -e "s|.*AuthPrincipal =.*|AuthPrincipal = host/kojihub@LOCAL|" \
        -e "s|.*AuthKeytab =.*|AuthKeytab = /share/koji.keytab|" \
        -e "s|.*KojiDebug =.*|KojiDebug = On|" \
        -e "s|.*LogLevel =.*|LogLevel = DEBUG|" \
        /etc/koji-hub/hub.conf

sed -i -e "s|LogLevel warn|LogLevel debug|" /etc/httpd/conf/httpd.conf

tee -a /etc/httpd/conf.d/kojihub.conf <<END
<Location /kojihub/ssllogin>
        AuthType GSSAPI
        GssapiSSLonly Off
        GssapiLocalName Off
        AuthName "GSSAPI Single Sign On Login"
        GssapiCredStore keytab:/share/koji.keytab
        Require valid-user
</Location>
END

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
fi

# ensure /mnt/koji is owned by apache
chown -R apache:apache /mnt/koji

# signal we are ready via a file
touch /share/hub.init

# run apache
httpd -DFOREGROUND
