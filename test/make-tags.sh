#!/usr/bin/sh
set -ux

. /etc/os-release

KOJI_SERVER=${KOJI_SERVER:-http://localhost:8080/kojihub}

KOJI="koji --server=${KOJI_SERVER} --user=kojiadmin --password=kojipass --authtype=password"

ARCHES=$(uname -m)
VERSION_MAJOR="${VERSION_ID%.*}"

TAG_NAME="${ID}${VERSION_MAJOR}"  # fedora35 or rhel8
TAG_BUILD="${TAG_NAME}-build"
TAG_CANDIDATE="${TAG_NAME}-candidate"

echo "Tag configuration: ${TAG_NAME}, ${TAG_BUILD}, ${TAG_CANDIDATE}, ${ARCHES}"

$KOJI add-tag "${TAG_NAME}"
$KOJI add-tag --parent "${TAG_NAME}" "${TAG_CANDIDATE}"
$KOJI add-tag --parent "${TAG_NAME}" --arches="${ARCHES}" "${TAG_BUILD}"
$KOJI add-target "${TAG_CANDIDATE}" "${TAG_BUILD}" "${TAG_CANDIDATE}"

$KOJI add-pkg --owner kojiadmin "${TAG_CANDIDATE}" fedora-guest
$KOJI add-pkg --owner kojiadmin "${TAG_CANDIDATE}" rhel-guest

$KOJI add-pkg --owner kojiadmin "${TAG_CANDIDATE}" fedora-iot

$KOJI add-pkg --owner kojiadmin "${TAG_CANDIDATE}" aws

$KOJI regen-repo "${TAG_BUILD}"
