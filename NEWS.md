# koji-osuild  - Koji and OSBuild integration


## CHANGES WITH 1:

  * Initial implementation of three plugins for the koji
    hub, the builder and command line client, which allows
    images and other OS artifacts to be built in composer
    via koji.

  * The *command line client* gained an `osbuild-image`
    sub-command that is very similar to `image-build`.
    It internally uses the new hub plugin to make a XML-RPC
    call, `osbuildImage` to request the building of a new
    image or artifact.

  * The *hub* plugin adds the `osbuildImage` XML-RPC method,
    verifies the parameters and then creates a new task of
    type `osbuildImage`.

  * The *builder* plugin does most of the work by adding a
    handler for `osbuildImage` tasks. It will use the new
    koji API of osbuild-composer version 21 to request a
    compose and wait until it is done. After a successful
    build the result will be tagged into the destination
    tag of the build target.

  * An integration test suite was added to CI that checks
    the end-to-end building of a cloud image on RHEL and
    Fedora.

  * Unit tests currently cover around 92% of the plugins.

  * Detailed instructions on how to run a local test setup
    are included in `HACKING.md`.


Contributions from: Christian Kellner, Lars Karlitski &
                    Tom Gundersen


— Berlin, 2020-09-30
