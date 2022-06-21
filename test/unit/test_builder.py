#
# koji hub plugin unit tests
#

#pylint: disable=too-many-lines

import configparser
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import uuid
import unittest.mock
from flexmock import flexmock
import requests

import koji
import httpretty

from plugintest import PluginTest


API_BASE = "api/image-builder-composer/v2/"

# https://github.com/osbuild/osbuild-composer
# internal/cloudapi/v2/openapi.v2.yml
# 631bd21ffeea03e7d4849f4d34430bde5a1b9db9
# Additionally, we include the test image type
# called `image_type`
VALID_IMAGE_TYPES = [
    "aws",
    "aws-rhui",
    "aws-ha-rhui",
    "aws-sap-rhui",
    "azure",
    "edge-commit",
    "edge-container",
    "edge-installer",
    "gcp",
    "guest-image",
    "image-installer",
    "vsphere",

    # test image type used as default
    "image_type"
]

# Simple HTTP proxy that counts requests that go through it.
# Definitely not production ready and standards complaint but it does the job.
# It does not support proxying HTTPS because httpretty cannot handle HTTP tunnelling.
class MockProxy:
    call_count = 0

    def register(self, uri):
        methods = [
            httpretty.GET,
            httpretty.PUT,
            httpretty.POST,
            httpretty.DELETE,
            httpretty.HEAD,
            httpretty.PATCH,
            httpretty.OPTIONS,
            httpretty.CONNECT
        ]
        for m in methods:
            httpretty.register_uri(
                m,
                re.compile(uri + "/.*"),
                body=self.handle
            )

    def handle(self, request, _uri, response_headers):
        self.call_count += 1
        r = requests.request(request.method, request.path, headers=request.headers, data=request.body)
        response_headers.update(r.headers)
        return [r.status_code, r.headers, r.text]


class MockComposer:  # pylint: disable=too-many-instance-attributes
    def __init__(self, url, *, architectures=None):
        self.url = urllib.parse.urljoin(url, API_BASE)
        self.architectures = architectures or ["x86_64"]
        self.composes = {}
        self.errors = []
        self.build_id = 1
        self.status = "success"
        self.routes = {}
        self.oauth = None
        self.oauth_check_delay = 0

    def httpretty_register(self):
        httpretty.register_uri(
            httpretty.POST,
            urllib.parse.urljoin(self.url, "compose"),
            body=self.compose_create
        )

    def next_build_id(self):
        build_id = self.build_id
        self.build_id += 1
        return build_id

    def compose_create(self, request, _uri, response_headers):
        check = self.oauth_check(request, response_headers)
        if check:
            return check

        content_type = request.headers.get("Content-Type")
        if content_type != "application/json":
            return [400, response_headers, "Bad Request"]

        js = json.loads(request.body)
        ireqs = js.get("image_requests")
        if not ireqs:
            return [400, response_headers, "Bad Request"]

        for it in ireqs:
            arch = it.get("architecture")
            if arch not in self.architectures:
                return [400, response_headers, "Unsupported Architrecture"]
            image_type = it.get("image_type")
            if not image_type or image_type not in VALID_IMAGE_TYPES:
                msg = f"Unsupported Image Type: '{image_type}'"
                return [400, response_headers, msg]

        compose_id = str(uuid.uuid4())
        build_id = self.next_build_id()
        compose = {
            "id": compose_id
        }

        self.composes[compose_id] = {
            "build_id": build_id,
            "request": js,
            "result": compose,
            "status": self.status,
            "routes": {
                "logs": 200,
                "manifests": 200
            }
        }

        httpretty.register_uri(
            httpretty.GET,
            urllib.parse.urljoin(self.url, "composes/" + compose_id),
            body=self.compose_status
        )

        httpretty.register_uri(
            httpretty.GET,
            urllib.parse.urljoin(self.url, "composes/" + compose_id + "/logs"),
            body=self.compose_logs
        )

        httpretty.register_uri(
            httpretty.GET,
            urllib.parse.urljoin(self.url, "composes/" + compose_id + "/manifests"),
            body=self.compose_manifests
        )

        return [201, response_headers, json.dumps(compose)]

    def compose_status(self, request, uri, response_headers):
        check = self.oauth_check(request, response_headers)
        if check:
            return check

        target = os.path.basename(uri)
        compose = self.composes.get(target)
        if not compose:
            return [400, response_headers, f"Unknown compose: {target}"]

        ireqs = compose["request"]["image_requests"]
        result = {
            "status": compose["status"],
            "koji_status": {
                "build_id": compose["build_id"],
            },
            "image_statuses": [
                {"status": compose["status"]} for _ in ireqs
            ]
        }
        return [200, response_headers, json.dumps(result)]

    def compose_logs(self, request, uri, response_headers):
        check = self.oauth_check(request, response_headers)
        if check:
            return check
        route = self.routes.get("logs")
        if route and route["status"] != 200:
            return [route["status"], response_headers, "Internal error"]

        target = os.path.basename(os.path.dirname(uri))
        compose = self.composes.get(target)
        if not compose:
            return [400, response_headers, f"Unknown compose: {target}"]

        ireqs = compose["request"]["image_requests"]
        result = {
            "image_builds": [
                {"osbuild": "log log log"} for _ in ireqs
            ],
            "koji": {
                "init": {"log": "yes, please!"},
                "import": {"log": "yes, indeed!"},
            }
        }
        return [200, response_headers, json.dumps(result)]

    def compose_manifests(self, request, uri, response_headers):
        check = self.oauth_check(request, response_headers)
        if check:
            return check

        route = self.routes.get("manifests")
        if route and route["status"] != 200:
            return [route["status"], response_headers, "Internal error"]

        target = os.path.basename(os.path.dirname(uri))
        compose = self.composes.get(target)
        if not compose:
            return [400, response_headers, f"Unknown compose: {target}"]

        ireqs = compose["request"]["image_requests"]
        result = {
            "manifests": [
                {"sources": {}, "pipelines": []} for _ in ireqs
            ]
        }
        return [200, response_headers, json.dumps(result)]

    def oauth_acquire_token(self, req, _uri, response_headers):

        data = urllib.parse.parse_qs(req.body.decode("utf-8"))

        grant_type = data.get("grant_type", [])
        if len(grant_type) != 1 or grant_type[0] != "client_credentials":
            return [400, response_headers, "Invalid grant type"]

        client_id = data.get("client_id", [])
        if len(client_id) != 1 or client_id[0] != "koji-osbuild":
            return [400, response_headers, "Invalid credentials"]

        client_secret = data.get("client_secret", [])
        if len(client_secret) != 1 or client_secret[0] != "s3cr3t":
            return [400, response_headers, "Invalid credentials"]

        token = {
            "access_token": str(uuid.uuid4()),
            "expires_in": 1,
            "token_type": "Bearer",
            "scope": "profile email",
        }

        reply = json.dumps(token)
        self.oauth = token

        token["created_at"] = time.time()

        return [200, response_headers, reply]

    def oauth_check(self, request, response_headers):
        if self.oauth is None:
            return None
        oauth = self.oauth

        auth = request.headers.get("authorization")
        if not auth or not auth.startswith("Bearer "):
            return [401, response_headers, "Unauthorized"]

        token = auth[7:]

        if oauth.get("access_token") != token:
            return [401, response_headers, "Unauthorized"]

        if self.oauth_check_delay:
            time.sleep(self.oauth_check_delay)
            # Reset it so that we can actually authorize at
            # the subsequent request
            self.oauth_check_delay = 0

        now = time.time()

        if oauth["created_at"] + oauth["expires_in"] < now:
            return [401, response_headers, "Token expired"]

        return None

    def oauth_activate(self, token_url: str):
        httpretty.register_uri(
            httpretty.POST,
            token_url,
            body=self.oauth_acquire_token
        )

        self.oauth = {}
        print("OAuth active!")


class UploadTracker:
    """Mock koji file uploading and keep track of uploaded files

    This assumes that `fast_incremental_upload` will be imported
    directly into the plugin namespace.
    """

    def __init__(self):
        self.uploads = {}

    def patch(self, plugin):
        setattr(plugin,
                "fast_incremental_upload",
                self._fast_incremental_upload)

    def _fast_incremental_upload(self, _session, name, fd, path, _tries, _log):
        upload = self.uploads.get(name, {"path": path})
        fd.seek(0, os.SEEK_END)
        upload["pos"] = fd.tell()
        self.uploads[name] = upload

    def assert_upload(self, name):
        if name not in self.uploads:
            raise AssertionError(f"Upload {name} missing")


class MockHost:
    """Mock for the HostExport koji class

    HostExport has the builder specific XML-RPC methods. This mocks a
    small subset of it. Currently the methods to support tagging a
    build are supported.
    The `tags` property, a mapping from build it to a list of tag ids,
    can be used see what tags were applied to a build id.
    """
    def __init__(self):
        self.tasks = {}
        self.waitset = {}
        self.count = 0
        self.tags = {}

    def subtask(self, method, arglist, parent, **opts):
        if method != "tagBuild":
            raise ValueError(f"{method} not mocked")

        task = {
            "method": method,
            "parent": parent,
            "arglist": arglist,
            "opts": opts,
            "result": True
        }

        self._tag_build(task)

        self.count += 1
        task_id = self.count
        self.tasks[task_id] = task

    def taskSetWait(self, parent, tasks):
        if tasks is None:
            tasks = [k for k, v in self.tasks.items() if v["parent"] == parent]
        self.waitset[parent] = tasks

    def taskWait(self, parent):
        tasks = self.waitset[parent]
        return tasks, []

    def taskWaitResults(self, parent, tasks, canfail=None):
        if canfail is None:
            canfail = []
        waitset = self.waitset[parent]
        selected = [t for t in waitset if t in tasks]
        res = {t: self.tasks[t]["result"] for t in selected}
        return res

    def _tag_build(self, task):
        assert task["parent"], "tagBuild: need parent"
        args = task["arglist"]
        assert 2 < len(args) < 6, "tagBuild: wrong argument number"
        tag = args[0]
        build = args[1]
        assert isinstance(tag, int), "tagBuild: tag id not int"
        assert isinstance(build, int), "tagBuild: build id not int"

        tags = self.tags.get(build, [])
        tags += [tag]
        self.tags[build] = tags


@PluginTest.load_plugin("builder")
class TestBuilderPlugin(PluginTest): # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self.uploads = UploadTracker()
        self.uploads.patch(self.plugin)

    @staticmethod
    def mock_session():

        host = MockHost()
        session = flexmock(host=host)

        build_target = {
            "build_tag": 23,
            "build_tag_name": "fedora-build",
            "dest_tag": 42,
            "dest_tag_name": "fedora-dest"
        }

        tag_info = {
            "id": build_target["dest_tag"],
            "name": build_target["dest_tag_name"],
            "locked": False
        }

        build_config = {
            "arches": "s390x aarch64 ppc64le x86_64"
        }

        repo_info = {
            "id": 20201015,
            "tag": build_target["build_tag_name"],
            "tag_id": build_target["build_tag"],
            "event_id": 2121,
        }

        session.should_receive("getBuildTarget") \
               .with_args("fedora-candidate", strict=True) \
               .and_return(build_target)

        session.should_receive('getBuildConfig') \
               .with_args(build_target["build_tag"]) \
               .and_return(build_config)

        session.should_receive("getTag") \
               .with_args(build_target["build_tag"], strict=True) \
               .and_return(tag_info)

        session.should_receive('getRepo') \
               .with_args(build_target["build_tag"]) \
               .and_return(repo_info)

        session.should_receive('getNextRelease') \
               .with_args(dict) \
               .and_return("20201015")

        return session

    @staticmethod
    def mock_options():
        options = flexmock(
            allowed_scms='pkg.osbuild.org:/*:no',
            workdir="/tmp",
            topurl="http://localhost/kojifiles"
        )
        return options

    def make_handler(self, *, config=None, session=None, options=None):
        if not session:
            session = self.mock_session()

        if not options:
            options = self.mock_options()

        def creator():
            return self.plugin.OSBuildImage(1,
                                            "osbuildImage",
                                            "params",
                                            session,
                                            options)

        if not config:
            return creator()

        with tempfile.TemporaryDirectory() as tmp:
            cfgfile = os.path.abspath(os.path.join(tmp, "ko.cfg"))
            with open(cfgfile, 'w', encoding="utf-8") as f:
                config.write(f)

            self.plugin.DEFAULT_CONFIG_FILES = [cfgfile]
            return creator()

    def test_plugin_config(self):

        composer_url = "https://image-builder.osbuild.org:2323"
        koji_url = "https://koji.osbuild.org/kojihub"
        certs = ["crt", "key"]
        ssl_cert = ", ".join(certs)
        ssl_verify = False

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
            "ssl_cert": ssl_cert,
            "ssl_verify": ssl_verify
        }
        cfg["koji"] = {
            "server": koji_url
        }


        handler = self.make_handler(config=cfg)

        self.assertEqual(handler.composer_url, composer_url)
        self.assertEqual(handler.koji_url, koji_url)
        session = handler.client.http
        self.assertEqual(session.cert, certs)
        self.assertEqual(session.verify, ssl_verify)

        # check we can handle a path in ssl_verify
        ssl_verify = "/a/path/to/a/ca"
        cfg["composer"]["ssl_verify"] = ssl_verify

        handler = self.make_handler(config=cfg)

        session = handler.client.http
        self.assertEqual(session.verify, ssl_verify)

        # check we can handle a plain ssl_cert string
        ssl_cert = "/a/path/to/a/cert"
        cfg["composer"]["ssl_cert"] = ssl_cert

        handler = self.make_handler(config=cfg)

        session = handler.client.http
        self.assertEqual(session.cert, ssl_cert)

        # check we handle detect wrong cert configs, i.e.
        # three certificate components
        cfg["composer"]["ssl_cert"] = "1, 2, 3"

        with self.assertRaises(ValueError):
            self.make_handler(config=cfg)

    def test_unknown_build_target(self):
        session = flexmock()

        session.should_receive("getBuildTarget") \
            .with_args("target", strict=True) \
            .and_return(None)

        options = flexmock(allowed_scms='pkg.osbuild.org:/*:no',
                           workdir="/tmp")
        handler = self.plugin.OSBuildImage(1,
                                           "osbuildImage",
                                           "params",
                                           session,
                                           options)

        args = ["name", "version", "distro",
                ["image_type"],
                "target",
                ["arches"],
                {}]

        with self.assertRaises(koji.BuildError):
            handler.handler(*args)

    def test_unsupported_architecture(self):
        session = flexmock()

        build_target = {
            "build_tag": "fedora-build",
            "name": "fedora-candidate",
            "dest_tag_name": "fedora-updates"
        }

        session.should_receive("getBuildTarget") \
               .with_args("fedora-candidate", strict=True) \
               .and_return(build_target) \
               .once()

        session.should_receive('getBuildConfig') \
               .with_args(build_target["build_tag"]) \
               .and_return({"arches": "x86_64"})

        options = flexmock(allowed_scms='pkg.osbuild.org:/*:no',
                           workdir="/tmp")

        handler = self.plugin.OSBuildImage(1,
                                           "osbuildImage",
                                           "params",
                                           session,
                                           options)

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["s390x"],
                {}]

        with self.assertRaises(koji.BuildError) as err:
            handler.handler(*args)
            self.assertTrue(str(err).startswith("Unsupported"))


    @httpretty.activate
    def test_bad_request(self):
        # Simulate a bad request by asking for an unsupported architecture
        handler = self.make_handler()

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["x86_64"],
                {}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["s390x"])
        composer.httpretty_register()

        with self.assertRaises(koji.GenericError):
            handler.handler(*args)

        self.uploads.assert_upload("compose-request.json")

    @httpretty.activate
    def test_compose_success(self):
        # Simulate a successful compose, check return value
        session = self.mock_session()
        handler = self.make_handler(session=session)

        arches = ["x86_64", "s390x"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=arches)
        composer.httpretty_register()

        res = handler.handler(*args)
        assert res, "invalid compose result"
        compose_id = res["composer"]["id"]
        compose = composer.composes.get(compose_id)
        self.assertIsNotNone(compose)

        ireqs = compose["request"]["image_requests"]

        # Check we got all the requested architectures
        ireq_arches = [i["architecture"] for i in ireqs]
        diff = set(arches) ^ set(ireq_arches)
        self.assertEqual(diff, set())

        for ir in ireqs:
            have = [r["baseurl"] for r in ir["repositories"]]
            self.assertEqual(have, repos)

        # check uploads: logs, compose request
        for arch in arches:
            self.uploads.assert_upload(f"{arch}-image_type.log.json")
            self.uploads.assert_upload(f"{arch}-image_type.manifest.json")
        self.uploads.assert_upload("compose-request.json")
        self.uploads.assert_upload("compose-status.json")
        self.uploads.assert_upload("koji-init.log.json")
        self.uploads.assert_upload("koji-import.log.json")

        build_id = res["koji"]["build"]
        # build should have been tagged
        self.assertIn(build_id, session.host.tags)

    @httpretty.activate
    def test_compose_failure(self):
        # Simulate a failed compose, check exception is raised
        session = self.mock_session()
        handler = self.make_handler(session=session)

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["x86_64"],
                {}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        composer.status = "failure"

        with self.assertRaises(koji.BuildError):
            handler.handler(*args)

        self.uploads.assert_upload("compose-request.json")
        self.uploads.assert_upload("x86_64-image_type.log.json")
        self.uploads.assert_upload("x86_64-image_type.manifest.json")
        self.uploads.assert_upload("compose-status.json")
        # build must not have been tagged
        self.assertEqual(len(session.host.tags), 0)

    @httpretty.activate
    def test_compose_no_logs(self):
        # Simulate fetching the logs fails, a non-fatal issue
        session = self.mock_session()
        handler = self.make_handler(session=session)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url)
        composer.httpretty_register()

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                composer.architectures,
                {}]

        composer.routes["logs"] = {
            "status": 500
        }

        res = handler.handler(*args)
        assert res, "invalid compose result"

        self.uploads.assert_upload("compose-request.json")

        with self.assertRaises(AssertionError):
            self.uploads.assert_upload("x86_64-image_type.log.json")

    @httpretty.activate
    def test_compose_no_manifest(self):
        # Simulate fetching the manifests fails, a non-fatal issue
        session = self.mock_session()
        handler = self.make_handler(session=session)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url)
        composer.httpretty_register()

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                composer.architectures,
                {}]

        composer.routes["manifests"] = {
            "status": 500
        }

        res = handler.handler(*args)
        assert res, "invalid compose result"

        self.uploads.assert_upload("compose-request.json")

        with self.assertRaises(AssertionError):
            self.uploads.assert_upload("x86_64-image_type.manifest.json")

    @httpretty.activate
    def test_kojiapi_image_types(self):
        # Simulate api requests with koji api image types
        session = self.mock_session()
        handler = self.make_handler(session=session)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url)
        composer.httpretty_register()

        for it in ("qcow2", "ec2", "ec2-ha", "ec2-sap"):
            args = ["name", "version", "distro",
                    [it],
                    "fedora-candidate",
                    composer.architectures,
                    {"skip_tag": True}]

            res = handler.handler(*args)
            assert res, "invalid compose result"

    @httpretty.activate
    def test_skip_tag(self):
        # Simulate a successful compose, where the tagging
        # should be skipped
        session = self.mock_session()
        handler = self.make_handler(session=session)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url)
        composer.httpretty_register()

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                composer.architectures,
                {"skip_tag": True}]

        res = handler.handler(*args)
        assert res, "invalid compose result"

        self.uploads.assert_upload("compose-request.json")

        # build must *not* have been tagged
        self.assertEqual(len(session.host.tags), 0)

    @httpretty.activate
    def test_cli_compose_success(self):
        # Check the basic usage of the plugin as a stand-alone client
        # for the osbuild-composer API
        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        certs = [
            "test/data/example-crt.pem",
            "test/data/example-key.pem"
        ]

        args = [
            "plugins/builder/osbuild.py",
            "--cert", ", ".join(certs),
            "--ca", "test/data/example-ca.pem",
            "compose",
            "Fedora-Cloud-Image",
            "33",
            "20201015.0",
            "fedora-33",
            "x86_64",
            "--repo", "http://download.localhost/pub/linux/$arch",
        ]

        with unittest.mock.patch.object(sys, 'argv', args):
            res = self.plugin.main()
            self.assertEqual(res, 0)

    @httpretty.activate
    def test_oauth2_fail_auth(self):
        composer_url = self.plugin.DEFAULT_COMPOSER_URL
        koji_url = self.plugin.DEFAULT_KOJIHUB_URL
        token_url = "https://localhost/token"

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
        }
        cfg["koji"] = {
            "server": koji_url
        }

        handler = self.make_handler(config=cfg)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        # initialize oauth
        composer.oauth_activate(token_url)

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["x86_64"],
                {}]

        with self.assertRaises(koji.GenericError):
            handler.handler(*args)

    @httpretty.activate
    def test_oauth2_basic(self):
        composer_url = self.plugin.DEFAULT_COMPOSER_URL
        koji_url = self.plugin.DEFAULT_KOJIHUB_URL
        token_url = "https://localhost/token"

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
        }
        cfg["composer:oauth"] = {
            "client_id": "koji-osbuild",
            "client_secret": "s3cr3t",
            "token_url": token_url
        }
        cfg["koji"] = {
            "server": koji_url
        }

        handler = self.make_handler(config=cfg)

        self.assertEqual(handler.composer_url, composer_url)
        self.assertEqual(handler.koji_url, koji_url)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        # initialize oauth
        composer.oauth_activate(token_url)

        arches = ["x86_64"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos}]

        res = handler.handler(*args)
        assert res, "invalid compose result"

    @httpretty.activate
    def test_proxy_http(self):
        # we need to use http because our proxy only supports proxying http requests
        composer_url = "http://localhost"
        koji_url = self.plugin.DEFAULT_KOJIHUB_URL
        # same here with http
        token_url = "http://localhost/token"
        proxy_url = "http://proxy.example.com"

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
            "proxy": proxy_url,
        }
        cfg["composer:oauth"] = {
            "client_id": "koji-osbuild",
            "client_secret": "s3cr3t",
            "token_url": token_url
        }
        cfg["koji"] = {
            "server": koji_url
        }

        handler = self.make_handler(config=cfg)

        self.assertEqual(handler.composer_url, composer_url)
        self.assertEqual(handler.koji_url, koji_url)

        url = "http://localhost"
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        proxy = MockProxy()
        proxy.register(proxy_url)

        # initialize oauth
        composer.oauth_activate(token_url)

        arches = ["x86_64"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos}]

        res = handler.handler(*args)

        # check that there are 5 proxy calls:
        # - oauth call
        # - compose create
        # - compose status
        # - compose manifest
        # - compose logs
        assert proxy.call_count == 5, "invalid proxy call count"
        assert res, "invalid compose result"

    def test_proxy_https(self):
        composer_url = self.plugin.DEFAULT_COMPOSER_URL
        koji_url = self.plugin.DEFAULT_KOJIHUB_URL
        proxy_url = "proxy.example.com"
        token_url = "https://localhost/token"

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
            "proxy": proxy_url,
        }
        cfg["composer:oauth"] = {
            "client_id": "koji-osbuild",
            "client_secret": "s3cr3t",
            "token_url": token_url
        }
        cfg["koji"] = {
            "server": koji_url
        }

        handler = self.make_handler(config=cfg)

        self.assertEqual(handler.client.http.proxies["http"], proxy_url)
        self.assertEqual(handler.client.http.proxies["https"], proxy_url)

    @httpretty.activate
    def test_oauth2_delay(self):
        composer_url = self.plugin.DEFAULT_COMPOSER_URL
        koji_url = self.plugin.DEFAULT_KOJIHUB_URL
        token_url = "https://localhost/token"

        cfg = configparser.ConfigParser()
        cfg["composer"] = {
            "server": composer_url,
        }
        cfg["composer:oauth"] = {
            "client_id": "koji-osbuild",
            "client_secret": "s3cr3t",
            "token_url": token_url
        }
        cfg["koji"] = {
            "server": koji_url
        }

        handler = self.make_handler(config=cfg)

        self.assertEqual(handler.composer_url, composer_url)
        self.assertEqual(handler.koji_url, koji_url)

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_register()

        # initialize oauth
        composer.oauth_activate(token_url)

        # have the token expire during the check
        composer.oauth_check_delay = 1.1

        arches = ["x86_64"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos}]

        res = handler.handler(*args)
        assert res, "invalid compose result"

    @httpretty.activate
    def test_customizations_compose(self):
        # Check we properly handle compose requests with customizations
        session = self.mock_session()
        handler = self.make_handler(session=session)

        customizations = {
            "packages": [
                "emacs"
            ]
        }

        arches = ["x86_64", "s390x"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos,
                 "customizations": customizations
                 }]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=arches)
        composer.httpretty_register()

        res = handler.handler(*args)
        assert res, "invalid compose result"
        compose_id = res["composer"]["id"]
        compose = composer.composes.get(compose_id)
        self.assertIsNotNone(compose)

        ireqs = compose["request"]["image_requests"]

        # Check we got all the requested architectures
        ireq_arches = [i["architecture"] for i in ireqs]
        diff = set(arches) ^ set(ireq_arches)
        self.assertEqual(diff, set())

        # Check we actually got the customizations
        self.assertEqual(compose["request"].get("customizations"),
                         customizations)

    @httpretty.activate
    def test_ostree_compose(self):
        # Check we properly handle ostree compose requests
        session = self.mock_session()
        handler = self.make_handler(session=session)

        arches = ["x86_64", "s390x"]
        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos,
                 "ostree": {
                     "parent": "osbuild/$arch/p",
                     "ref": "osbuild/$arch/r",
                     "url": "https://osbuild.org/repo"
                 }}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=arches)
        composer.httpretty_register()

        res = handler.handler(*args)
        assert res, "invalid compose result"
        compose_id = res["composer"]["id"]
        compose = composer.composes.get(compose_id)
        self.assertIsNotNone(compose)

        ireqs = compose["request"]["image_requests"]

        # Check we got all the requested architectures
        ireq_arches = [i["architecture"] for i in ireqs]
        diff = set(arches) ^ set(ireq_arches)
        self.assertEqual(diff, set())

        for ir in ireqs:
            assert "ostree" in ir
            ostree = ir["ostree"]
            for key in ("parent", "ref", "url"):
                assert key in ostree
            assert ostree["url"] == "https://osbuild.org/repo"

        ireq_parents = [i["ostree"]["parent"] for i in ireqs]
        diff = set(f"osbuild/{a}/p" for a in arches) ^ set(ireq_parents)
        self.assertEqual(diff, set())

        ireq_refs = [i["ostree"]["ref"] for i in ireqs]
        diff = set(f"osbuild/{a}/r" for a in arches) ^ set(ireq_refs)
        self.assertEqual(diff, set())

    @httpretty.activate
    def test_compose_repo_complex(self):
        # Check we properly handle ostree compose requests
        session = self.mock_session()
        handler = self.make_handler(session=session)

        arches = ["x86_64", "s390x"]
        repos = [
            {"baseurl": "https://first.repo/$arch",
             "package_sets": ["a", "b", "c", "d"]},
            {"baseurl": "https://second.repo/$arch",
             "package_sets": ["alpha"]},
            {"baseurl": "https://third.repo/$arch"}
        ]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                arches,
                {"repo": repos}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=arches)
        composer.httpretty_register()

        res = handler.handler(*args)
        assert res, "invalid compose result"
        compose_id = res["composer"]["id"]
        compose = composer.composes.get(compose_id)
        self.assertIsNotNone(compose)

        ireqs = compose["request"]["image_requests"]

        # Check we got all the requested architectures
        ireq_arches = [i["architecture"] for i in ireqs]
        diff = set(arches) ^ set(ireq_arches)
        self.assertEqual(diff, set())

        for ir in ireqs:
            arch = ir["architecture"]
            repos = ir["repositories"]
            assert len(repos) == 3

            for r in repos:
                baseurl = r["baseurl"]
                assert baseurl.endswith(arch)
                if baseurl.startswith("https://first.repo"):
                    ps = r.get("package_sets")
                    assert ps and ps == ["a", "b", "c", "d"]
