#!/bin/bash
set -euo pipefail

# Colorful output.
function greenprint {
  echo -e "\033[1;32m${1}\033[0m"
}

# Get OS and architecture details.
source /etc/os-release
ARCH=$(uname -m)

# Mock configuration file to use for building RPMs.
MOCK_CONFIG="${ID}-${VERSION_ID%.*}-$(uname -m)"

# The commit we are testing
GIT_SHA=$(git rev-parse HEAD)

# Bucket in S3 where our artifacts are uploaded
REPO_BUCKET=osbuild-composer-repos

# Public URL for the S3 bucket with our artifacts.
MOCK_REPO_BASE_URL="http://${REPO_BUCKET}.s3-website.us-east-2.amazonaws.com"

# Distro version in whose buildroot was the RPM built.
DISTRO_VERSION=${ID}-${VERSION_ID}

if [[ "$ID" == rhel ]] && sudo subscription-manager status; then
  # If this script runs on a subscribed RHEL, the RPMs are actually built
  # using the latest CDN content, therefore rhel-*-cdn is used as the distro
  # version.
  DISTRO_VERSION=rhel-${VERSION_ID%.*}-cdn
fi

# Relative path of the repository – used for constructing both the local and
# remote paths below, so that they're consistent.
REPO_PATH=koji-osbuild/${DISTRO_VERSION}/${ARCH}/${GIT_SHA}

# Directory to hold the RPMs temporarily before we upload them.
REPO_DIR=repo/${REPO_PATH}

# Full URL to the RPM repository after they are uploaded.
REPO_URL=${MOCK_REPO_BASE_URL}/${REPO_PATH}

# Don't rerun the build if it already exists
if curl --silent --fail --head --output /dev/null "${REPO_URL}/repodata/repomd.xml"; then
  greenprint "🎁 Repository already exists. Exiting."
  exit 0
fi

# Mock is only available in EPEL for RHEL.
if [[ $ID == rhel ]] && ! rpm -q epel-release; then
    greenprint "📦 Setting up EPEL repository"
    curl -Ls --retry 5 --output /tmp/epel.rpm \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo rpm -Uvh /tmp/epel.rpm
fi

# Install requirements for building RPMs in mock.
greenprint "📦 Installing mock requirements"
sudo dnf -y install createrepo_c mock s3cmd

# Print some data.
greenprint "🧬 Using mock config: ${MOCK_CONFIG}"
greenprint "📦 Git SHA: ${GIT_SHA}"
greenprint "📤 RPMS will be uploaded to: ${REPO_URL}"

greenprint "🔧 Building source RPM"
git archive --prefix "koji-osbuild-${GIT_SHA}/" --output "koji-osbuild-${GIT_SHA}.tar.gz" HEAD
sudo mock -v -r "$MOCK_CONFIG" --buildsrpm \
  --define "commit ${GIT_SHA}" \
  --spec ./koji-osbuild.spec \
  --sources "./koji-osbuild-${GIT_SHA}.tar.gz" \
  --resultdir ./srpm

greenprint "🎁 Building RPMs"
sudo mock -v -r $MOCK_CONFIG \
  --define "commit ${GIT_SHA}" \
  --with=tests \
  --resultdir $REPO_DIR \
  srpm/*.src.rpm

# Change the ownership of all of our repo files from root to our CI user.
sudo chown -R $USER ${REPO_DIR%%/*}

greenprint "  Remove logs from mock build"
rm ${REPO_DIR}/*.log

# Create a repo of the built RPMs.
greenprint "⛓️ Creating dnf repository"
createrepo_c ${REPO_DIR}

# Upload repository to S3.
greenprint "☁ Uploading RPMs to S3"
pushd repo
    AWS_ACCESS_KEY_ID="$V2_AWS_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$V2_AWS_SECRET_ACCESS_KEY" \
    s3cmd --acl-public put --recursive . s3://${REPO_BUCKET}/
popd
