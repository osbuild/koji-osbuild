#!/bin/bash
set -ux

KOJI="koji --server=http://org.osbuild.koji.koji/kojihub --user=kojiadmin --password=kojipass --authtype=password"

$KOJI add-host org.osbuild.koji.kojid i386 x86_64

if [ $? -eq 0 ]; then
  $KOJI add-host-to-channel org.osbuild.koji.kojid image
fi

/usr/sbin/kojid -d -v -f --force-lock || cat /var/log/kojid.log
