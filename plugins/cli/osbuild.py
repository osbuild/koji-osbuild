"""Koji osbuild integration - koji client plugin

This koji plugin provides a new 'osbuild-image' command for the koji
command line tool. It uses the 'osbuildImage' XMLRPC endpoint, that
is provided by the koji osbuild plugin for the koji hub.
"""


from pprint import pprint

import koji
import koji_cli.lib as kl
from koji.plugin import export_cli
from koji_cli.lib import _


def parse_args(argv):
    usage = _("usage: %prog osbuild-image [options] <name> <version> "
              "<distro> <target> <arch> [<arch> ...]")

    parser = kl.OptionParser(usage=kl.get_usage_str(usage))

    parser.add_option("--nowait", action="store_false", dest="wait",
                      help=_("Don't wait on image creation"))
    parser.add_option("--release", help=_("Forcibly set the release field"))
    parser.add_option("--repo", action="append",
                      help=_("Specify a repo that will override the repo used to install "
                             "RPMs in the image. May be used multiple times. The "
                             "build tag repo associated with the target is the default."))
    parser.add_option("--image-type", metavar="TYPE",
                      help='Request an image-type [default: qcow2]',
                      type=str, action="append", default=[])
    parser.add_option("--wait", action="store_true",
                      help=_("Wait on the image creation, even if running in the background"))

    opts, args = parser.parse_args(argv)
    if len(args) < 5:
        parser.error(_("At least five arguments are required: a name, "
                       "a version, a distribution, a build target, "
                       "and 1 or more architectures."))

    for i, arg in enumerate(("name", "version", "distro", "target")):
        setattr(opts, arg, args[i])
    setattr(opts, "arch", args[4:])

    return opts


def check_target(session, name: str):
    """Check the target with name exists and has a destination tag"""

    target = session.getBuildTarget(name)
    if not target:
        raise koji.GenericError(_("Unknown build target: %s" % name))

    tag = session.getTag(target['dest_tag'])
    if not tag:
        raise koji.GenericError(_("Unknown destination tag: %s" %
                                  target['dest_tag_name']))


@export_cli
def handle_osbuild_image(options, session, argv):
    "[build] Build images via osbuild"
    args = parse_args(argv)

    name, version, arch, target = args.name, args.version, args.arch, args.target
    distro, image_types = args.distro, args.image_type

    if not image_types:
        image_types = ["qcow2"]

    opts = {}

    if args.release:
        opts["release"] = args.release

    if args.repo:
        opts["repo"] = ",".join(args.repo)

    # Do some early checks to be able to give quick feedback
    check_target(session, target)

    if not options.quiet:
        print("name:", name)
        print("version:", version)
        print("distro:", distro)
        print("arches:", ", ".join(arch))
        print("target:", target)
        print("image types ", str(image_types))
        pprint(opts)

    kl.activate_session(session, options)

    task_id = session.osbuildImage(name, version, distro, image_types, target, arch, opts=opts)

    if not options.quiet:
        print("Created task: %s" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))

    if (args.wait is None and kl._running_in_bg()) or args.wait is False:
        # either running in the background or must not wait by user's
        # request. All done.
        return None

    session.logout()
    res = kl.watch_tasks(session, [task_id], quiet=options.quiet)

    if res == 0:
        result = session.getTaskResult(task_id)
        print(result)
    return res
