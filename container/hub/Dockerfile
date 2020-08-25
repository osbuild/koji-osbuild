FROM quay.io/osbuild/koji:latest

COPY container/hub/hub.conf /etc/koji-hub/hub.conf
COPY plugins/hub/osbuild.py /usr/lib/koji-hub-plugins/
COPY container/hub/run-hub.sh /app/run-hub.sh

ENTRYPOINT /app/run-hub.sh
