#!/bin/bash
set -eux

koji --server=http://localhost/kojihub \
     --user=kojiadmin \
     --password=kojipass \
     --authtype=password \
     add-host kojid i386 x86_64 || true

koji --server=http://localhost/kojihub \
     --user=kojiadmin \
     --password=kojipass \
     --authtype=password \
     add-host-to-channel kojid image || true

/usr/sbin/kojid -d -v -f --force-lock || cat /var/log/kojid.log
