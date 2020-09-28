#!/usr/bin/sh
set -ux

KOJI="koji --server=http://localhost:8080/kojihub --user=kojiadmin --password=kojipass --authtype=password"

$KOJI add-tag f32
$KOJI add-tag --parent f32 f32-candidate
$KOJI add-tag --parent f32 --arches=x86_64 f32-build
$KOJI add-target f32-candidate f32-build f32-candidate

$KOJI add-pkg --owner kojiadmin f32-candidate Fedora-Cloud
$KOJI add-pkg --owner kojiadmin f32-candidate RHEL-Cloud

$KOJI regen-repo f32-build
