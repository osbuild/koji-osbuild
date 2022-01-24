#!/usr/bin/python3
"""Koji osbuild integration - builder plugin

This koji builder plugin provides a handler for 'osbuildImage' tasks,
which will create compose requests via osbuild composer's koji API.

Included is a basic pure-python client for composers koji API based
on the corresponding OpenAPI. Although manually crafted it follows
its terminology closely.
This client is used in the `OSBuildImage`, which provides the actual
koji integration to talk to composer.

This file can also be used as an executable where it acts as a stand
alone client for composer's API.
"""


import configparser
import enum
import io
import json
import sys
import time
import urllib.parse

from string import Template
from typing import Dict, List

import requests
import koji

from koji.daemon import fast_incremental_upload
from koji.tasks import BaseTaskHandler


DEFAULT_COMPOSER_URL = "https://localhost"
DEFAULT_KOJIHUB_URL = "https://localhost/kojihub"
DEFAULT_CONFIG_FILES = [
    "/usr/share/koji-osbuild/builder.conf",
    "/etc/koji-osbuild/builder.conf"
]

API_BASE = "api/composer-koji/v1/"

# The following classes are a implementation of osbuild composer's
# koji API. It is based on the corresponding OpenAPI specification
# version '1' and should model it closely.

class Repository:
    def __init__(self, baseurl: str, gpgkey: str = None):
        self.baseurl = baseurl
        self.gpgkey = gpgkey

    def as_dict(self, arch: str = ""):
        tmp = Template(self.baseurl)
        url = tmp.substitute(arch=arch)
        res = {"baseurl": url}
        if self.gpgkey:
            res["gpgkey"] = self.gpgkey
        return res


class ImageRequest:
    def __init__(self, arch: str, image_type: str, repos: List):
        self.architecture = arch
        self.image_type = image_type
        self.repositories = repos

    def as_dict(self):
        arch = self.architecture
        return {
            "architecture": self.architecture,
            "image_type": self.image_type,
            "repositories": [
                repo.as_dict(arch) for repo in self.repositories
            ]
        }


class NVR:
    def __init__(self, name: str, version: str, release: str):
        self.name = name
        self.version = version
        self.release = release

    def as_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "release": self.release
        }

    def __str__(self):
        return f"nvr: {self.name}, {self.version}, {self.release}"


class ComposeRequest:
    class Koji:
        def __init__(self, server: str, task_id: int):
            self.server = server
            self.task_id = task_id

    # pylint: disable=redefined-outer-name
    def __init__(self, nvr: NVR, distro: str, ireqs: List[ImageRequest], koji: Koji):
        self.nvr = nvr
        self.distribution = distro
        self.image_requests = ireqs
        self.koji = koji

    def as_dict(self):
        return {
            **self.nvr.as_dict(),
            "distribution": self.distribution,
            "koji": {
                "server": str(self.koji.server),
                "task_id": self.koji.task_id
            },
            "image_requests": [
                img.as_dict() for img in self.image_requests
            ]
        }


class ImageStatus(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    BUILDING = "building"
    UPLOADING = "uploading"


class ComposeStatus:
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    REGISTERING = "registering"

    def __init__(self, status: str, images: List, task_id: int, build_id):
        self.status = status
        self.images = images
        self.koji_task_id = task_id
        self.koji_build_id = build_id

    @classmethod
    def from_dict(cls, data: Dict):
        status = data["status"].lower()
        koji_task_id = data["koji_task_id"]
        koji_build_id = data.get("koji_build_id")
        images = [
            ImageStatus(s["status"].lower()) for s in data["image_statuses"]
        ]
        return cls(status, images, koji_task_id, koji_build_id)

    def as_dict(self):
        data = {
            "status": self.status,
            "koji_task_id": self.koji_task_id,
            "image_statuses": [
                {"status": status.value} for status in self.images
            ]
        }

        if self.koji_build_id is not None:
            data["koji_build_id"] = self.koji_build_id

        return data

    @property
    def is_finished(self):
        if self.is_success:
            return True
        return self.status in [self.FAILURE]

    @property
    def is_success(self):
        return self.status in [self.SUCCESS]


class ComposeLogs:
    def __init__(self, image_logs: List, import_logs, init_logs):
        self.image_logs = image_logs
        self.koji_import_logs = import_logs
        self.koji_init_logs = init_logs

    @classmethod
    def from_dict(cls, data: Dict):
        image_logs = data["image_logs"]
        import_logs = data["koji_import_logs"]
        init_logs = data["koji_init_logs"]
        return cls(image_logs, import_logs, init_logs)


class Client:
    def __init__(self, url):
        self.server = url
        self.url = urllib.parse.urljoin(url, API_BASE)
        self.http = requests.Session()

    @staticmethod
    def parse_certs(string):
        certs = [s.strip() for s in string.split(',')]
        count = len(certs)
        if count == 1:
            return certs[0]
        if count > 2:
            msg = f"Invalid cert string '{string}' ({count} certs)"
            raise ValueError(msg)

        return certs

    def compose_create(self, compose_request: ComposeRequest):
        url = urllib.parse.urljoin(self.url, "compose")

        data = compose_request.as_dict()
        res = self.http.post(url, json=data)

        if res.status_code != 201:
            body = res.content.decode("utf-8").strip()
            msg = f"Failed to create the compose request: {body}"
            raise koji.GenericError(msg) from None

        ps = res.json()
        return ps["id"]  # the compose id

    def compose_status(self, compose_id: str):
        url = urllib.parse.urljoin(self.url, f"compose/{compose_id}")

        res = self.http.get(url)

        if res.status_code != 200:
            body = res.content.decode("utf-8").strip()
            msg = f"Failed to get the compose status: {body}"
            raise koji.GenericError(msg) from None

        return ComposeStatus.from_dict(res.json())

    def compose_logs(self, compose_id: str):
        url = urllib.parse.urljoin(self.url, f"compose/{compose_id}/logs")

        res = self.http.get(url)

        if res.status_code != 200:
            body = res.content.decode("utf-8").strip()
            msg = f"Failed to get the compose logs: {body}"
            raise koji.GenericError(msg) from None

        return ComposeLogs.from_dict(res.json())

    def compose_manifests(self, compose_id: str):
        url = urllib.parse.urljoin(self.url, f"compose/{compose_id}/manifests")

        res = self.http.get(url)

        if res.status_code != 200:
            body = res.content.decode("utf-8").strip()
            msg = f"Failed to get the compose manifests: {body}"
            raise koji.GenericError(msg) from None

        return res.json()

    def wait_for_compose(self, compose_id: str, *, sleep_time=2, callback=None):
        while True:
            status = self.compose_status(compose_id)
            if callback:
                callback(status)

            if status.is_finished:
                return status

            time.sleep(sleep_time)


class OSBuildImage(BaseTaskHandler):
    Methods = ['osbuildImage']
    _taskWeight = 2.0

    def __init__(self, task_id, method, params, session, options):
        super().__init__(task_id, method, params, session, options)

        cfg = configparser.ConfigParser()
        cfg.read_dict({
            "composer": {"server": DEFAULT_COMPOSER_URL},
            "koji": {"server": DEFAULT_KOJIHUB_URL}
        })

        cfg.read(DEFAULT_CONFIG_FILES)

        self.composer_url = cfg["composer"]["server"]
        self.koji_url = cfg["koji"]["server"]
        self.client = Client(self.composer_url)

        self.logger.debug("composer: %s", self.composer_url)
        self.logger.debug("koji: %s", self.composer_url)

        composer = cfg["composer"]

        if "ssl_cert" in composer:
            data = cfg["composer"]["ssl_cert"]
            cert = self.client.parse_certs(data)
            self.client.http.cert = cert
            self.logger.debug("ssl cert: %s", cert)

        if "ssl_verify" in composer:
            try:
                val = composer.getboolean("ssl_verify")
            except ValueError:
                val = composer["ssl_verify"]

            self.client.http.verify = val
            self.logger.debug("ssl verify: %s", val)

    def upload_json(self, data: Dict, name: str):
        fd = io.StringIO()
        json.dump(data, fd, indent=4, sort_keys=True)
        fd.seek(0)
        path = koji.pathinfo.taskrelpath(self.id)
        fast_incremental_upload(self.session,
                                name + ".json",
                                fd,
                                path,
                                3,  # retries
                                self.logger)

    def attach_logs(self, compose_id: str, ireqs: ImageRequest):
        self.logger.debug("Fetching logs")

        try:
            logs = self.client.compose_logs(compose_id)
        except koji.GenericError as e:
            self.logger.warning("Failed to fetch logs: %s", str(e))
            return

        if logs.koji_init_logs:
            self.upload_json(logs.koji_init_logs, "koji-init.log")

        if logs.koji_import_logs:
            self.upload_json(logs.koji_import_logs, "koji-import.log")

        ilogs = zip(logs.image_logs, ireqs)
        for log, ireq in ilogs:
            name = "%s-%s.log" % (ireq.architecture, ireq.image_type)
            self.logger.debug("Uploading logs: %s", name)
            self.upload_json(log, name)

    def attach_manifests(self, compose_id: str, ireqs: ImageRequest):
        self.logger.debug("Fetching manifests")

        try:
            manifests = self.client.compose_manifests(compose_id)
        except koji.GenericError as e:
            self.logger.warning("Failed to fetch manifests: %s", str(e))
            return

        imanifests = zip(manifests, ireqs)
        for manifest, ireq in imanifests:
            name = "%s-%s.manifest" % (ireq.architecture, ireq.image_type)
            self.logger.debug("Uploading manifest: %s", name)
            self.upload_json(manifest, name)

    @staticmethod
    def arches_for_config(buildconfig: Dict):
        archstr = buildconfig["arches"]
        if not archstr:
            name = buildconfig["name"]
            raise koji.BuildError(f"Missing arches for tag '%{name}'")
        return set(koji.canonArch(a) for a in archstr.split())

    def make_repos_for_target(self, target_info):
        repo_info = self.getRepo(target_info['build_tag'])
        if not repo_info:
            return None
        self.logger.debug("repo info: %s", str(repo_info))
        path_info = koji.PathInfo(topdir=self.options.topurl)
        repourl = path_info.repo(repo_info['id'], target_info['build_tag_name'])
        self.logger.debug("repo url: %s", repourl)
        return [Repository(repourl + "/$arch")]

    def make_repos_for_user(self, repos):
        self.logger.debug("user repo override: %s", str(repos))
        return [Repository(r) for r in repos]

    def tag_build(self, tag, build_id):
        args = [
            tag,       # tag id
            build_id,  # build id
            False,     # force
            None,      # from tag
            True       # ignore_success (not sending notification)
        ]

        task = self.session.host.subtask(method='tagBuild',
                                         arglist=args,
                                         label='tag',
                                         parent=self.id,
                                         arch='noarch')
        self.wait(task)

    def on_status_update(self, status: ComposeStatus):
        self.upload_json(status.as_dict(), "compose-status")

    # pylint: disable=arguments-differ
    def handler(self, name, version, distro, image_types, target, arches, opts):
        """Main entry point for the task"""
        self.logger.debug("Building image via osbuild %s, %s, %s, %s",
                          name, str(arches), str(target), str(opts))

        self.logger.debug("Task id: %s", str(self.id))

        target_info = self.session.getBuildTarget(target, strict=True)
        if not target_info:
            raise koji.BuildError(f"Target '{target}' not found")

        build_tag = target_info['build_tag']
        buildconfig = self.session.getBuildConfig(build_tag)

        # Architectures
        tag_arches = self.arches_for_config(buildconfig)
        diff = set(arches) - tag_arches
        if diff:
            raise koji.BuildError("Unsupported architecture(s): " + str(diff))

        # Repositories
        repo_urls = opts.get("repo")
        if repo_urls:
            repos = self.make_repos_for_user(repo_urls)
        else:
            repos = self.make_repos_for_target(target_info)

        client = self.client

        # Version and names
        nvr = NVR(name, version, opts.get("release"))
        if not nvr.release:
            nvr.release = self.session.getNextRelease(nvr.as_dict())

        # Arches and image types
        ireqs = [ImageRequest(a, i, repos) for a in arches for i in image_types]
        self.logger.debug("Creating compose: %s (%s)\n  koji: %s\n  images: %s",
                          nvr, distro, self.koji_url,
                          str([i.as_dict() for i in ireqs]))

        # Setup done, create the compose request and send it off
        kojidata = ComposeRequest.Koji(self.koji_url, self.id)
        request = ComposeRequest(nvr, distro, ireqs, kojidata)

        self.upload_json(request.as_dict(), "compose-request")

        cid = client.compose_create(request)
        self.logger.info("Compose id: %s", cid)

        self.logger.debug("Waiting for comose to finish")
        status = client.wait_for_compose(cid, callback=self.on_status_update)

        self.logger.debug("Compose finished: %s", str(status.as_dict()))
        self.logger.info("Compose result: %s", status.status)

        self.attach_manifests(cid, ireqs)
        self.attach_logs(cid, ireqs)

        if not status.is_success:
            raise koji.BuildError(f"Compose failed (id: {cid})")

        # Successful compose, must have a build id associated
        bid = status.koji_build_id

        # Build was successful, tag it
        if not opts.get('skip_tag'):
            self.tag_build(target_info["dest_tag"], bid)

        result = {
            "composer": {
                "server": self.composer_url,
                "id": cid
            },
            "koji": {
                "build": bid
            }
        }
        return result


# Stand alone osbuild composer API client executable
RESET = "\033[0m"
GREEN = "\033[32m"
BOLD = "\033[1m"
RED = "\033[31m"


def show_compose(cs):
    print(f"status: {BOLD}{cs.status}{RESET}")
    print("koji task: " + str(cs.koji_task_id))
    if cs.koji_build_id is not None:
        print("koji build: " + str(cs.koji_build_id))
    print("images: ")
    for image in cs.images:
        print("  " + str(image))


def compose_cmd(client: Client, args):
    nvr = NVR(args.name, args.version, args.release)
    images = []
    formats = args.format or ["qcow2"]
    repos = [Repository(url) for url in args.repo]
    for fmt in formats:
        for arch in args.arch:
            ireq = ImageRequest(arch, fmt, repos)
            images.append(ireq)

    kojidata = ComposeRequest.Koji(args.koji, 0)
    request = ComposeRequest(nvr, args.distro, images, kojidata)
    cid = client.compose_create(request)

    print(f"Compose: {cid}")
    while True:
        status = client.compose_status(cid)
        print(f"status: {status.status: <10}\r", end="")
        if status.is_finished:
            break

        time.sleep(2)

    show_compose(status)
    return 0


def status_cmd(client: Client, args):
    cs = client.compose_status(args.id)
    show_compose(cs)
    return 0


def wait_cmd(client: Client, args):
    cs = client.wait_for_compose(args.id)
    show_compose(cs)
    return 0


def main():
    import argparse  # pylint: disable=import-outside-toplevel

    parser = argparse.ArgumentParser(description="osbuild composer koji API client")
    parser.add_argument("--url", metavar="URL", type=str,
                        default=DEFAULT_COMPOSER_URL,
                        help="The URL of the osbuild composer koji API endpoint")
    parser.set_defaults(cmd=None)
    sp = parser.add_subparsers(help='commands')

    subpar = sp.add_parser("compose", help='create a new compose')
    subpar.add_argument("name", metavar="NAME", help='The name')
    subpar.add_argument("version", metavar="VERSION", help='The version')
    subpar.add_argument("release", metavar="RELEASE", help='The release')
    subpar.add_argument("distro", metavar="DISTRO", help='The distribution')
    subpar.add_argument("repo", metavar="REPO", help='The repository to use',
                        type=str, action="append", default=[])
    subpar.add_argument("arch", metavar="ARCHITECTURE", help='Request the architecture',
                        type=str, nargs="+")
    subpar.add_argument("--format", metavar="FORMAT", help='Request the image format [qcow2]',
                        action="append", type=str, default=[])
    subpar.add_argument("--koji", metavar="URL", help='The koji url',
                        default=DEFAULT_KOJIHUB_URL)
    subpar.add_argument("--cert", metavar="cert", help='The client SSL certificates to use',
                        type=str)
    subpar.add_argument("--ca", metavar="ca", help='The SSL certificate authority',
                        type=str)
    subpar.set_defaults(cmd='compose')

    subpar = sp.add_parser("status", help='status of a compose')
    subpar.add_argument("id", metavar="COMPOSE_ID", help='compose id')
    subpar.set_defaults(cmd='status')

    subpar = sp.add_parser("wait", help='wait for a compose')
    subpar.add_argument("id", metavar="COMPOSE_ID", help='compose id')
    subpar.set_defaults(cmd='wait')

    args = parser.parse_args()

    if not args.cmd:
        print(f"{RED}Error{RESET}: Need command\n")
        parser.print_help(sys.stderr)
        return 1

    client = Client(args.url)

    if args.cert:
        print("Using client certificates")
        client.http.cert = client.parse_certs(args.cert)
        client.http.verify = True

    if args.ca:
        client.http.verify = args.ca

    if args.cmd == "compose":
        return compose_cmd(client, args)
    if args.cmd == "status":
        return status_cmd(client, args)
    if args.cmd == "wait":
        return wait_cmd(client, args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
