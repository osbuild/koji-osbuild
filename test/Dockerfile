FROM docker.io/library/fedora:latest

RUN dnf -y upgrade \
    && dnf -y \
            --setopt=fastestmirror=True \
            --setopt=install_weak_deps=False \
            install \
	koji-builder \
	koji-hub \
	koji-utils \
	koji \
	postgresql \
	pylint \
	python3-flexmock \
	python3-httpretty \
	python3-jsonschema \
	python3-pytest-cov \
	python3-pytest \
	python3-koji \
	python3-requests \
	&& dnf clean all

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
