# Koji osbuild

This project provides osbuild integration with Koji. This is done via three
plugins:

 - Koji **hub** plugin: Provides a new XMLRPC API endpoint that clients
   can use to create new `osbuildImage` Koji tasks.
 - Koji **builder** plugin: Handles `osbuildImage` Koji tasks and will talk
   to osbuild-composer to create new composes via composer's Koji API.
 - Koji **cli** plugin: Adds a new `osbuild-command` to the existing `koji`
   command line client. This will then use the new XMLRPC API to request a
   new compose.

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

Create the tag infrastructure:
```
./make-tags.sh
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

## Creating a compose
The `compose.py` client can be used to create a compose via the koji plugins:
```
./compose.py --plain fedora 32 f32-candidate x86_64 --repo 'http://download.fedoraproject.org/pub/fedora/linux/releases/32/Everything/$arch/os/'
```

## Development

### Useful links

- [koji source](https://pagure.io/koji/tree/master)
- [koji plugin howto](https://docs.pagure.org/koji/writing_a_plugin/)
- [koji server howto](https://docs.pagure.org/koji/server_howto/)
- [koji server bootstrap](https://docs.pagure.org/koji/server_bootstrap/)
- [osbs koji plugin](https://github.com/containerbuildsystem/koji-containerbuild/)
