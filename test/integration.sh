#!/bin/bash
set -euxo pipefail

function greenprint {
    echo -e "\033[1;32m${1}\033[0m"
}

# Get OS data.
source /etc/os-release

if [[ $ID == rhel ]] && ! rpm -q epel-release; then
    greenprint "📦 Setting up EPEL repository"
    curl -Ls --retry 5 --output /tmp/epel.rpm \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo rpm -Uvh /tmp/epel.rpm
fi

greenprint "Fetching RPMs"
sudo mkdir -p /tmp/osbuild-composer-koji-test/rpms
sudo dnf -y \
     --downloadonly \
     --downloaddir=/tmp/osbuild-composer-koji-test/rpms \
     download \
     "koji-osbuild*"

greenprint "Creating composer SSL certificates"
sudo /usr/libexec/koji-osbuild-tests/make-certs.sh /usr/share/koji-osbuild-tests

greenprint "Building containers"
sudo /usr/libexec/koji-osbuild-tests/build-container.sh /usr/share/koji-osbuild-tests

greenprint "Starting containers"
sudo /usr/libexec/koji-osbuild-tests/run-koji-container.sh start

greenprint "Print logs"
sudo podman logs org.osbuild.koji.koji

greenprint "Testing Koji hub API access"
koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello

greenprint "Copying credentials, certificates and configuration files"
sudo -E /usr/libexec/koji-osbuild-tests/copy-creds.sh /usr/share/koji-osbuild-tests

greenprint "Starting mock OpenID server"
sudo /usr/libexec/koji-osbuild-tests/run-openid.sh start

greenprint "Starting osbuild-composer's Cloud API socket and a remote worker"
# Start services.
sudo systemctl stop 'osbuild*'
# make sure that the local worker is not running
sudo systemctl mask osbuild-worker@1.service
# enable remote worker API
sudo systemctl start osbuild-remote-worker.socket
# enable Cloud API
sudo systemctl start osbuild-composer-api.socket
# start a remote worker
sudo systemctl start osbuild-remote-worker@localhost:8700.service

greenprint "Watching worker logs"
WORKER_UNIT=$(sudo systemctl list-units | grep -o -E "osbuild.*worker.*\.service")
sudo journalctl -af -n 1 -u "${WORKER_UNIT}" &
WORKER_JOURNAL_PID=$!

greenprint "Starting koji builder"
sudo /usr/libexec/koji-osbuild-tests/run-builder.sh start /usr/share/koji-osbuild-tests

greenprint "Creating Koji tag infrastructure"
/usr/libexec/koji-osbuild-tests/make-tags.sh

greenprint "Running integration tests"
# export environment variables for the Boto3 client to work out of the box
AWS_ACCESS_KEY_ID="${V2_AWS_ACCESS_KEY_ID:-}" \
AWS_SECRET_ACCESS_KEY="${V2_AWS_SECRET_ACCESS_KEY:-}" \
python3 -m unittest discover -v /usr/libexec/koji-osbuild-tests/integration/

greenprint "Stop watching worker logs"
sudo pkill -P ${WORKER_JOURNAL_PID}

greenprint "Stopping koji builder"
sudo /usr/libexec/koji-osbuild-tests/run-builder.sh stop /usr/share/koji-osbuild-tests

greenprint "Stopping containers"
sudo /usr/libexec/koji-osbuild-tests/run-koji-container.sh stop

greenprint "Stopping mock OpenID server"
sudo /usr/libexec/koji-osbuild-tests/run-openid.sh stop

greenprint "Removing generated CA cert"
sudo rm /etc/pki/ca-trust/source/anchors/osbuild-ca-crt.pem
sudo update-ca-trust
