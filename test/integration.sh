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

greenprint "Installing required packages"
sudo dnf -y install \
    container-selinux \
    dnsmasq \
    jq \
    krb5-workstation \
    koji \
    koji-osbuild-cli \
    podman

if [[ $ID == rhel ]]; then
  greenprint "Tweaking podman, maybe."
  sudo cp schutzbot/vendor/87-podman-bridge.conflist /etc/cni/net.d/
  sudo cp schutzbot/vendor/dnsname /usr/libexec/cni/
fi

greenprint "Fetching RPMs"
sudo mkdir -p /tmp/osbuild-composer-koji-test/rpms
sudo dnf -y \
     --downloadonly \
     --downloaddir=/tmp/osbuild-composer-koji-test/rpms \
     download \
     "koji-osbuild*"

greenprint "Creating composer SSL certificates"
sudo test/make-certs.sh

greenprint "Building containers"
sudo podman build -t koji.hub -f container/hub/Dockerfile.${ID} .
sudo podman build -t koji.builder -f container/builder/Dockerfile.${ID} .

greenprint "Starting containers"
sudo test/run-koji-container.sh start

greenprint "Print logs"
sudo podman logs org.osbuild.koji.koji

greenprint "Copying credentials and certificates"
sudo test/copy-creds.sh

greenprint "Testing Koji hub API access"
koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello

greenprint "Starting koji builder"
sudo ./run-builder.sh start

greenprint "Creating Koji tag infrastructure"
test/make-tags.sh

greenprint "Running integration tests"
python3 -m unittest discover -v test/integration/

greenprint "Stopping koji builder"
sudo ./run-builder.sh stop

greenprint "Stopping containers"
sudo test/run-koji-container.sh stop

greenprint "Removing generated CA cert"
sudo rm \
    /etc/pki/ca-trust/source/anchors/koji-ca-crt.pem
sudo update-ca-trust
