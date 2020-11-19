# koji-osuild  - Koji and OSBuild integration

## CHANGES WITH 3:

  * Ship tests in koji-osbuild-tests package. The tests got
    reworked so that they can be installed and run from the
    installation. This will be useful for reverse dependency
    testing, i.e. testing the plugins from other projects,
    like composer as well as in gating tests.

  * Add the ability to skip the tagging. An new command line
    option, `--skip-tag` is added, which translate into an
    a new field in the options for the hub and builder. If
    that option is present, the builder plugin will skip the
    tagging step.

  * builder plugin: the compose status is attached to the
    koji task as `compose-status.json` and updated whenever
    it is fetched from composer. This allows to follow the
    individual image builds.

  * builder plugin: The new logs API, introduce in composer
    version 24, is used to fetch and attach build logs as
    well as the koji init/import logs.

  * builder plugin: Support for the dynamic build ids, i.e.
    don't use the koji build id returned from the compose
    request API call but use the new `koji_build_id` field
    included in the compose status response.
    This makes koji-osbuild depend on osbuild composer 24!

  * test: lots of improvements to the tests and ci, e.g.
    using the quay mirror for the postgres container or
    matching the container versions to the host.

Contributions from: Christian Kellner, Lars Karlitski,
                    Ondřej Budai

— Berlin, 2020-11-19

## CHANGES WITH 2:

  * Fix the logic in the builder plugin that checks that
    all requested architectures for a requested build are
    indeed supported by the build tag. The existing check
    had its operands mixed up.

  * Fix the spec file so that the builder package now
    depends on python3-jsonschema.

  * Adapt the CI for a podman package change: previously
    the podman-plugins package, which contains the dnsname
    plugin, was automatically pulled in on Fedora. This
    changed recently which in turn broke our Fedora
    integration test. Explicitly install podman-plugins.

  * CI: Integrate codespell spell-checking.

  * Small fixes for the README.md.

Contributions from: Christian Kellner, Tomas Kopecek

— Berlin, 2020-11-03

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
