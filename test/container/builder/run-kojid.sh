#!/bin/bash
set -ux

if ls /share/rpms/*.rpm 1> /dev/null 2>&1; then
  echo "Using RPMs"
  rm /usr/lib/koji-builder-plugins/osbuild.py
  rpm -i /share/rpms/koji-osbuild-?-0.*.rpm \
         /share/rpms/koji-osbuild-builder-*.rpm
fi

KOJI="koji --server=http://org.osbuild.koji.koji/kojihub --user=kojiadmin --password=kojipass --authtype=password"

$KOJI add-host org.osbuild.koji.kojid i386 x86_64

if [ $? -eq 0 ]; then
  $KOJI add-host-to-channel org.osbuild.koji.kojid image
  $KOJI add-host-to-channel org.osbuild.koji.kojid createrepo
fi

/usr/sbin/kojid -d -v -f --force-lock || cat /var/log/kojid.log
