#!/usr/bin/bash
set -euo pipefail

SHELLCHECK_SEVERITY=${SHELLCHECK_SEVERITY:-warning}

run_test() {
  podman run -it -v "$(pwd)":/github/workspace:z --env "GITHUB_WORKSPACE=/github/workspace" koji.test "$1"
}

pushd test
podman build -t koji.test -f Dockerfile .
popd

SCRIPTS="$(git ls-files --exclude='*.sh' --ignored | xargs echo)"

run_test "shellcheck -S ${SHELLCHECK_SEVERITY} ${SCRIPTS}"
run_test "pytest -v --cov-report=term --cov=osbuild test/unit/"
run_test "pylint plugins/**/*.py test/**/*.py"
