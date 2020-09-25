# Testing

## Unit tests

To support local development an container `test/Dockerfile` contains
the environment to test all three plugins. It can be built and run
via `./run-test.sh`. This will execute the unit tests as well as
run pylint and ShellCheck on the source code.

## Local integration testing

### Preparation

This assumes that osbuild-composer, version greater than 21, is
installed on the host and the koji API is enabled.

Make certificates for osbuild-composer. This is needed to authorize
clients to use the composer API. There is a script that will create
the certificates and also copy it to the correct places in `/etc`.

```
sudo test/make-certs.sh
```

Build the containers:
```
sudo test/build-container.sh
```

### Setup the infrastructure containers

Run the infra containers, i.e. the database server, the kerberos kdc,
and koji hub. This will also create the kerberos keytabs needed for
the koji builder to authorize itself to koji hub.

```
sudo ./run-koji-container.sh start
```

Koji web will now be running at: http://localhost/koji/


Copy the credentials: The TLS certificates for the koji builder plugin
to make authorize requests to composer and the kerberos keytabs
needed for composer and worker (of composer) to reserve and import the
build via the koji XML RPC.

```
sudo  test/copy-creds.sh
```

### Run the koji builder

Run the koji builder instance can be started. Here `fg` means that
it will be running in the foreground, so logs can be inspected and
the container stopped via `ctrl+c`.

```
sudo ./run-builder.sh fg
```

### Setup the tags

In order to build an image, a series of tags needs to be created.
Specifically:

 * the target tag
 * the build tag, which contains the architectures
 * destination tag, which contains the list of packages

A helper script will create a minimum set that is necessary to build
an image call `Fedora-Cloud` for `f32-candidate`:

```
./make-tags.sh
```

### Client plugin

The client plugin needs to be installed either by creating the RPMs
first via meson, or via a symlink from the checkout to the koji cli
plugin directory:

```
mkdir -p /usr/lib/python3.8/site-packages/koji/koji_cli_plugins/
ln -s plugins/cli/osbuild.py \
	  /usr/lib/python3.8/site-packages/koji/koji_cli_plugins/osbuild.py
```

### Making a build

Now that all is setup a build can be created via:

```
koji --server=http://localhost/kojihub \
     --user=kojiadmin \
	 --password=kojipass \
	 --authtype=password \
	 osbuild-image \
	 Fedora-Cloud \
	 32 \
	 fedora-32 \
	 f32-candidate \
	 x86_64 \
	 --repo 'http://download.fedoraproject.org/pub/fedora/linux/releases/32/Everything/$arch/os/' \
	 --image-type qcow2 \
	 --release 1
```

## Useful links

- [koji source](https://pagure.io/koji/tree/master)
- [koji plugin howto](https://docs.pagure.org/koji/writing_a_plugin/)
- [koji server howto](https://docs.pagure.org/koji/server_howto/)
- [koji server bootstrap](https://docs.pagure.org/koji/server_bootstrap/)
- [osbs koji plugin](https://github.com/containerbuildsystem/koji-containerbuild/)
