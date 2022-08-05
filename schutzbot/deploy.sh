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
OSBUILD_COMMIT=376cbffd136bc4ba86fc7c63697fa5b88fe3acef             # release 62
OSBUILD_COMPOSER_COMMIT=2d13050ba84a2bb30d9dd980639ee78354fe90f3    # release 59-dev (includes mock openid server fix)

# Get OS details.
source /etc/os-release
ARCH=$(uname -m)

# Koji is only available in EPEL for RHEL.
if [[ $ID == rhel ]] && ! rpm -q epel-release; then
    curl -Ls --retry 5 --output /tmp/epel.rpm \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo rpm -Uvh /tmp/epel.rpm
fi

if [[ "$ID" == rhel ]] && sudo subscription-manager status; then
  # If this script runs on subscribed RHEL, install content built using CDN
  # repositories.
  DISTRO_VERSION=rhel-${VERSION_ID%.*}-cdn

  # workaround for https://github.com/osbuild/osbuild/issues/717
  sudo subscription-manager config --rhsm.manage_repos=1
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
name=koji-osbuild ${CI_COMMIT_SHA}
baseurl=${DNF_REPO_BASEURL}/koji-osbuild/${DISTRO_VERSION}/${ARCH}/${CI_COMMIT_SHA}
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
