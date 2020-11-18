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

# HACK: podman-plugins was only recently added to RHEL. Fetch it from the
# internal RHEL 8.3.1 repository until that is released.
greenprint "Install the podman dnsname plugin"
if [[ $ID == rhel ]]; then
  sudo tee /etc/yum.repos.d/rhel-8-3-1.repo << EOF
[rhel-8-3-1]
name = RHEL 8.3.1 override
baseurl = http://download.devel.redhat.com/rhel-8/nightly/RHEL-8/RHEL-8.3.1-20201118.n.0/compose/AppStream/x86_64/os
enabled = 0
gpgcheck = 1
EOF

  sudo dnf -y install '--disablerepo=*' --enablerepo=rhel-8-3-1 podman-plugins
else
  sudo dnf -y install podman-plugins
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
sudo test/build-container.sh

greenprint "Starting containers"
sudo test/run-koji-container.sh start

greenprint "Print logs"
sudo podman logs org.osbuild.koji.koji

greenprint "Copying credentials and certificates"
sudo test/copy-creds.sh

greenprint "Testing Koji hub API access"
koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello

greenprint "Starting koji builder"
sudo test/run-builder.sh start

greenprint "Creating Koji tag infrastructure"
test/make-tags.sh

greenprint "Running integration tests"
python3 -m unittest discover -v test/integration/

greenprint "Stopping koji builder"
sudo test/run-builder.sh stop

greenprint "Stopping containers"
sudo test/run-koji-container.sh stop

greenprint "Removing generated CA cert"
sudo rm /etc/pki/ca-trust/source/anchors/osbuild-ca-crt.pem
sudo update-ca-trust
