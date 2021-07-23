#!/bin/bash
set -euxo pipefail

function retry {
    local count=0
    local retries=5
    until "$@"; do
        exit=$?
        count=$(($count + 1))
        if [[ $count -lt $retries ]]; then
            echo "Retrying command..."
            sleep 1
        else
            echo "Command failed after ${retries} retries. Giving up."
            return $exit
        fi
    done
    return 0
}

# Variables for where to find osbuild-composer RPMs to test against
DNF_REPO_BASEURL=http://osbuild-composer-repos.s3-website.us-east-2.amazonaws.com
OSBUILD_COMMIT=35de3093a7b52569512bdc61d2105febbb9b0c7e             # release 30
OSBUILD_COMPOSER_COMMIT=b5987a5ca51826f29a3bce742d693a55f16f016f    # commit newer than release 30 (we need one with rhel-8-cdn)

# Get OS details.
source /etc/os-release
ARCH=$(uname -m)

# Koji is only available in EPEL for RHEL.
if [[ $ID == rhel ]] && ! rpm -q epel-release; then
    curl -Ls --retry 5 --output /tmp/epel.rpm \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo rpm -Uvh /tmp/epel.rpm
fi

# Register RHEL if we are provided with a registration script.
if [[ -n "${RHN_REGISTRATION_SCRIPT:-}" ]] && ! sudo subscription-manager status; then
    sudo chmod +x $RHN_REGISTRATION_SCRIPT
    sudo $RHN_REGISTRATION_SCRIPT
fi

# Enable fastestmirror to speed up dnf operations.
echo -e "fastestmirror=1" | sudo tee -a /etc/dnf/dnf.conf

# Add osbuild team ssh keys.
cat schutzbot/team_ssh_keys.txt | tee -a ~/.ssh/authorized_keys > /dev/null

# Distro version in whose buildroot was the RPM built.
DISTRO_VERSION=${ID}-${VERSION_ID}

if [[ "$ID" == rhel ]] && sudo subscription-manager status; then
  # If this script runs on a subscribed RHEL, the RPMs are actually built
  # using the latest CDN content, therefore rhel-*-cdn is used as the distro
  # version.
  DISTRO_VERSION=rhel-${VERSION_ID%.*}-cdn
fi

# Set up dnf repositories with the RPMs we want to test
sudo tee /etc/yum.repos.d/osbuild.repo << EOF
[koji-osbuild]
name=koji-osbuild ${GIT_COMMIT}
baseurl=${DNF_REPO_BASEURL}/koji-osbuild/${DISTRO_VERSION}/${ARCH}/${GIT_COMMIT}
enabled=1
gpgcheck=0
# Default dnf repo priority is 99. Lower number means higher priority.
priority=5

[osbuild]
name=osbuild ${OSBUILD_COMMIT}
baseurl=${DNF_REPO_BASEURL}/osbuild/${DISTRO_VERSION}/${ARCH}/${OSBUILD_COMMIT}
enabled=1
gpgcheck=0
# Default dnf repo priority is 99. Lower number means higher priority.
priority=5

[osbuild-composer]
name=osbuild-composer ${OSBUILD_COMPOSER_COMMIT}
baseurl=${DNF_REPO_BASEURL}/osbuild-composer/${DISTRO_VERSION}/${ARCH}/${OSBUILD_COMPOSER_COMMIT}
enabled=1
gpgcheck=0
# Default dnf repo priority is 99. Lower number means higher priority.
priority=5
EOF

# Installing koji-osbuild-tests package
retry sudo dnf -y install koji-osbuild-tests

# Start services.
sudo systemctl enable --now osbuild-composer.socket
sudo systemctl enable --now osbuild-composer-api.socket
