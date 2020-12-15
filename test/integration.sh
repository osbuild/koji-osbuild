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

# HACK: podman-plugins was only recently added to RHEL. Fetch it from the
# RHEL 8.4.0 snapshot until 8.3.1 released (we don't do z-stream snapshots).
# On Fedora, podman-plugins is installed in the koji-osbuild-tests package.
# Please adjust the spec file to do the same on RHEL before removing this block.
greenprint "Install the podman dnsname plugin"
if [[ $ID == rhel ]]; then
  sudo tee /etc/yum.repos.d/rhel-8-4-0.repo << EOF
[rhel-8-4-0]
name = RHEL 8.4.0 override
baseurl = https://rpmrepo.osbuild.org/v1/psi/el8/el8-x86_64-appstream-8.4.0.n-20201201
enabled = 0
gpgcheck = 1
EOF

  sudo dnf -y install '--disablerepo=*' --enablerepo=rhel-8-4-0 podman-plugins
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

greenprint "Starting osbuild-composer's socket"
sudo systemctl enable --now osbuild-composer-api.socket

greenprint "Building containers"
sudo /usr/libexec/koji-osbuild-tests/build-container.sh /usr/share/koji-osbuild-tests

greenprint "Starting containers"
sudo /usr/libexec/koji-osbuild-tests/run-koji-container.sh start

greenprint "Print logs"
sudo podman logs org.osbuild.koji.koji

greenprint "Copying credentials and certificates"
sudo /usr/libexec/koji-osbuild-tests/copy-creds.sh /usr/share/koji-osbuild-tests

greenprint "Testing Koji hub API access"
koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello

greenprint "Starting koji builder"
sudo /usr/libexec/koji-osbuild-tests/run-builder.sh start /usr/share/koji-osbuild-tests

greenprint "Creating Koji tag infrastructure"
/usr/libexec/koji-osbuild-tests/make-tags.sh

greenprint "Running integration tests"
python3 -m unittest discover -v /usr/libexec/koji-osbuild-tests/integration/

greenprint "Stopping koji builder"
sudo /usr/libexec/koji-osbuild-tests/run-builder.sh stop /usr/share/koji-osbuild-tests

greenprint "Stopping containers"
sudo /usr/libexec/koji-osbuild-tests/run-koji-container.sh stop

greenprint "Removing generated CA cert"
sudo rm /etc/pki/ca-trust/source/anchors/osbuild-ca-crt.pem
sudo update-ca-trust
