#!/usr/bin/bash
set -euo pipefail

SHELLCHECK_SEVERITY=${SHELLCHECK_SEVERITY:-warning}

run_test() {
  if [ -f /.dockerenv ]; then
    eval "$1"
    return
  fi

  podman run --rm -it -v "$(pwd)":/github/workspace:z --env "GITHUB_WORKSPACE=/github/workspace" koji.test "$1"
}

if [ ! -f /.dockerenv ]; then
  pushd test
  podman build -t koji.test -f Dockerfile .
  popd
else
  echo "Container detected, direct mode."
fi

SCRIPTS="$(git ls-files --exclude='*.sh' --ignored --cached | xargs echo)"

run_test "shellcheck -S ${SHELLCHECK_SEVERITY} ${SCRIPTS}"
run_test "pytest -v --cov-report=term --cov=osbuild test/unit/"
run_test "pylint plugins/**/*.py test/**/*.py"
