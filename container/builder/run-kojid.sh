#!/bin/bash
set -eux

koji --server=http://org.osbuild.koji.koji/kojihub \
     --user=kojiadmin \
     --password=kojipass \
     --authtype=password \
     add-host org.osbuild.koji.kojid i386 x86_64 || true

koji --server=http://org.osbuild.koji.koji/kojihub \
     --user=kojiadmin \
     --password=kojipass \
     --authtype=password \
     add-host-to-channel org.osbuild.koji.kojid image || true

/usr/sbin/kojid -d -v -f --force-lock || cat /var/log/kojid.log
