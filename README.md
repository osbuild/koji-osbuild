podman pull docker.io/library/postgres:12-alpine

podman pod create --name koji -p 5432 -p 8080:80
podman run --rm -p 5432:5432 --env-file env postgres:12-alpine


podman build -t koji-server .
podman run --env-file env --pod koji -p 80:8080 koji-server


koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello


podman build -t koji.builder -f container/builder/Dockerfile .
podman run -it --rm --env-file container/env --pod koji -v (pwd)/container/ssl/:/share/ssl:Z -v (pwd)/mnt:/mnt:Z --name koji.builder koji.builder

koji add-host-to-channel b1 image

podman run -it --rm --env-file container/env --pod koji -v (pwd)/container/ssl/:/share/ssl:Z -v (pwd)/mnt:/mnt:Z --name koji.builder koji.builder
