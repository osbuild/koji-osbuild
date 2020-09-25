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

## Development

See [`HACKING.md`](HACKING.md) for how to develop and test this project.
