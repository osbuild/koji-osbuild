#!/bin/sh -l
set -euo pipefail

cd $GITHUB_WORKSPACE

/bin/bash -o errexit -c "$1"
