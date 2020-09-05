
## Building the containers

```sh
# container for the hub
sudo podman build -t koji.hub -f container/hub/Dockerfile .

# container for the builder
sudo podman build -t koji.builder -f container/builder/Dockerfile .
```

## Running

Run the database server, the kerberos kdc, and koji hub:
```
sudo ./run-koji-container.sh start
```

Run the koji builder:
```
sudo ./run-builder.sh
```

## Verify installation

Try connecting to koji hub locally via the `koji` command line client:
```
koji --server=http://localhost:80/kojihub --user=osbuild --password=osbuildpass --authtype=password hello
grüezi, osbuild!

You are using the hub at http://localhost:80/kojihub
Authenticated via password
```

Check logs
```
sudo podman logs org.osbuild.koji.koji  # koji hub
sudo podman logs org.osbuild.koji.kdc   # kerberos kdc
```

Execute into the container:
```
sudo podman exec -it org.osbuild.koji.koji /bin/bash
sudo podman exec -it org.osbuild.koji.kdc /bin/bash
sudo podman exec -it org.osbuild.koji.kojid /bin/bash
```

koji --server=http://localhost:8080/kojihub --user=osbuild --password=osbuildpass --authtype=password hello
