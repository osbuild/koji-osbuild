#!/usr/bin/bash
set -euo pipefail


run_test() {
  podman run -it -v $(pwd):/github/workspace:z --env "GITHUB_WORKSPACE=/github/workspace" koji.test "$1"
}

pushd test
podman build -t koji.test -f Dockerfile .
popd

run_test "python3 -m unittest discover -v test/unit/"
run_test "pylint test/**/*.py"
