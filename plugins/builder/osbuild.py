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
import sys
import time
import urllib.parse

from string import Template
from typing import Dict, List

import requests
import koji

from koji.tasks import BaseTaskHandler


DEFAULT_COMPOSER_URL = "http://localhost:8701/"
DEFAULT_KOJIHUB_URL = "https://localhost/kojihub"
DEFAULT_CONFIG_FILES = [
    "/usr/share/koji-osbuild/builder.conf",
    "/etc/koji-osbuild/builder.conf"
]


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

    def __init__(self, status: str, images: List, koji_task_id: str):
        self.status = status
        self.images = images
        self.koji_task_id = koji_task_id

    @classmethod
    def from_dict(cls, data: Dict):
        status = data["status"].lower()
        koji_task_id = data["koji_task_id"]
        images = [ImageStatus(s["status"].lower()) for s in data["image_statuses"]]
        return cls(status, images, koji_task_id)

    @property
    def is_finished(self):
        if self.is_success:
            return True
        return self.status in [self.FAILURE]

    @property
    def is_success(self):
        return self.status in [self.SUCCESS]


class Client:
    def __init__(self, url):
        self.url = url
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

    def compose_create(self, nvr: NVR, distro: str, images: List[ImageRequest], kojidata: ComposeRequest.Koji):
        url = urllib.parse.urljoin(self.url, f"/compose")
        cro = ComposeRequest(nvr, distro, images, kojidata)

        res = self.http.post(url, json=cro.as_dict())

        if res.status_code != 201:
            body = res.content.strip()
            msg = f"Failed to create the compose request: {body}"
            raise koji.GenericError(msg) from None

        ps = res.json()
        compose_id, koji_build_id = ps["id"], ps["koji_build_id"]
        return compose_id, koji_build_id

    def compose_status(self, compose_id: str):
        url = urllib.parse.urljoin(self.url, f"/compose/{compose_id}")

        res = self.http.get(url)

        if res.status_code != 200:
            body = res.content.strip()
            msg = f"Failed to get the compose status: {body}"
            raise koji.GenericError(msg) from None

        return ComposeStatus.from_dict(res.json())

    def wait_for_compose(self, compose_id: str, *, sleep_time=2):
        while True:
            status = self.compose_status(compose_id)
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
            "composer": {"url": DEFAULT_COMPOSER_URL},
            "koji": {"url": DEFAULT_KOJIHUB_URL}
        })

        cfg.read(DEFAULT_CONFIG_FILES)

        self.composer_url = cfg["composer"]["url"]
        self.koji_url = cfg["koji"]["url"]
        self.client = Client(self.composer_url)

        composer = cfg["composer"]

        if "ssl_cert" in composer:
            data = cfg["composer"]["ssl_cert"]
            cert = self.client.parse_certs(data)
            self.client.http.cert = cert

        if "ssl_verify" in composer:
            try:
                val = composer.getboolean("ssl_verify")
            except ValueError:
                val = composer["ssl_verify"]

            self.client.http.verify = val

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
        arches = set(arches)
        diff = tag_arches - arches
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

        # Setup down, talk to composer to create the compose
        kojidata = ComposeRequest.Koji(self.koji_url, self.id)
        cid, bid = client.compose_create(nvr, distro, ireqs, kojidata)
        self.logger.info("Compose id: %s", cid)

        self.logger.debug("Waiting for comose to finish")
        status = client.wait_for_compose(cid)

        if not status.is_success:
            self.logger.error("Compose failed: %s", str(status))
            return {
                'koji_builds': []
            }

        return {
            'koji_builds': [bid],
            'composer_id': cid,
            'build': bid,
        }


# Stand alone osbuild composer API client executable
RESET = "\033[0m"
GREEN = "\033[32m"
BOLD = "\033[1m"
RED = "\033[31m"


def show_compose(cs):
    print(f"status: {BOLD}{cs.status}{RESET}")
    print("koji task: " + str(cs.koji_task_id))
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
    cid, bid = client.compose_create(nvr, args.distro, images, kojidata)

    print(f"Compose: {cid} [koji build id: {bid}]")
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
    subpar.add_argument("version", metavar="NAME", help='The version')
    subpar.add_argument("release", metavar="RELEASE", help='The release')
    subpar.add_argument("distro", metavar="NAME", help='The distribution')
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
