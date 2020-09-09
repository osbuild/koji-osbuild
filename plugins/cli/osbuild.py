"""osbild koji command line client integration"""
import koji_cli.lib as kl
from koji.plugin import export_cli
from koji_cli.lib import _


def parse_args(argv):
    usage = _("usage: %prog osbuild-image [options] <name> <version> "
              "<distro> <target> <arch> [<arch> ...]")

    parser = kl.OptionParser(usage=kl.get_usage_str(usage))

    parser.add_option("--release", help=_("Forcibly set the release field"))
    parser.add_option("--repo", action="append",
                      help=_("Specify a repo that will override the repo used to install "
                             "RPMs in the image. May be used multiple times. The "
                             "build tag repo associated with the target is the default."))
    parser.add_option("--image-type", metavar="TYPE",
                      help='Request an image-type [default: qcow2]',
                      type=str, action="append", default=[])

    opts, args = parser.parse_args(argv)
    if len(args) < 5:
        parser.error(_("At least five arguments are required: a name, "
                       "a version, a distribution, a build target, "
                       "and 1 or more architectures."))

    for i, arg in enumerate(("name", "version", "distro", "target")):
        setattr(opts, arg, args[i])
    setattr(opts, "arch", args[4:])

    return opts


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

    print("name:", name)
    print("version:", version)
    print("distro:", distro)
    print("arches:", ", ".join(arch))
    print("target:", target)
    print("image types ", str(image_types))

    kl.activate_session(session, options)

    task_id = session.osbuildImage(name, version, distro, image_types, target, arch, opts=opts)

    print("Created task: %s" % task_id)
    print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))

    res = kl.watch_tasks(session, [task_id], quiet=False)

    if res == 0:
        result = session.getTaskResult(task_id)
        print(result)
