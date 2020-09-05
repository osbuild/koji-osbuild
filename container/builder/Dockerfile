FROM docker.io/library/fedora:latest

RUN dnf -y upgrade \
    && dnf -y \
            --setopt=fastestmirror=True \
            --setopt=install_weak_deps=False \
            install \
	koji-builder \
	koji-utils \
	createrepo_c \
	postgresql \
	python3-koji \
	&& dnf clean all

COPY container/builder/kojid.conf /etc/kojid/kojid.conf
COPY plugins/builder/osbuild.py /usr/lib/koji-builder-plugins/
COPY container/builder/run-kojid.sh /app/run-kojid.sh
COPY container/builder/osbuild.krb5.conf /etc/krb5.conf.d/

ENTRYPOINT /app/run-kojid.sh
