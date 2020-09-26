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

## Configuration

The builder plugin needs to be configured via a `builder.conf` file that
can be located in either `/usr/share/koji-osbuild` or `/etc/koji-osbuild`.

```ini
[composer]
# The host, port and transport (https vs http) of osbuild composer
# NB: The 'https' transport is required for SSL/TLS authorization
server = https://composer.osbuild.org

# Authorization via client side certificates: can be either a pair of
# certificate and key files separated by comma or a file combining both.
ssl_cert = /share/worker-crt.pem, /share/worker-key.pem

# Verification of the server side: either a boolean (True / False) to
# enable or disable verification, or a path to a CA_BUNDLE file or a
# directory containing certificates of trusted CAs.
ssl_verify = /share/worker-ca.pem

[koji]
# The URL to the koji hub XML-RPC endpoint
server = https://koji.fedoraproject.org/kojihub
```


## Development

See [`HACKING.md`](HACKING.md) for how to develop and test this project.
