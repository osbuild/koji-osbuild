#!/usr/bin/sh
set -ux

KOJI="koji --server=http://localhost/kojihub --user=kojiadmin --password=kojipass --authtype=password"

$KOJI add-tag f32
$KOJI add-tag --parent f32 f32-candidate
$KOJI add-tag --parent f32 --arches=i686,x86_64 f32-build
$KOJI add-target f32-candidate f32-build f32-candidate

$KOJI regen-repo f32-build
