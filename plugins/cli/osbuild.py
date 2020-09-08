"""osbild koji command line client integration"""
import argparse
import koji_cli.lib as kl
from koji.plugin import export_cli
from koji_cli.lib import _


def parse_args(argv):
    parser = argparse.ArgumentParser(description="osbuild koji client")
    parser.add_argument("--repo", metavar="REPO", help='The repository to use',
                        type=str, action="append", default=[])
    parser.add_argument("--release", metavar="RELEASE", help='The distribution release')
    parser.add_argument("name", metavar="NAME", help='The distribution name')
    parser.add_argument("version", metavar="VERSION", help='The distribution version')
    parser.add_argument("distro", metavar="DISTRO", help='The distribution')
    parser.add_argument("target", metavar="TARGET", help='The build target')
    parser.add_argument("arch", metavar="ARCH", help='Request the architecture',
                        type=str, nargs="+")
    parser.add_argument("--image-type", metavar="TYPE",
                        help='Request an image-type [default: qcow2]',
                        type=str, action="append", default=[])
    args = parser.parse_args(argv)
    return args


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
