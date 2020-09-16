#
# koji hub plugin unit tests
#

import configparser
import json
import os
import sys
import tempfile
import uuid
import unittest.mock
from flexmock import flexmock

import koji
import httpretty

from plugintest import PluginTest


class MockComposer:
    def __init__(self, url, *, architectures=["x86_64"]):
        self.url = url
        self.architectures = architectures[:]
        self.composes = {}
        self.errors = []
        self.build_id = 1

    def httpretty_regsiter(self):
        httpretty.register_uri(
            httpretty.POST,
            self.url + "compose",
            body=self.compose_create
        )

    def next_build_id(self):
        build_id = self.build_id
        self.build_id += 1
        return build_id

    def compose_create(self, request, _uri, response_headers):
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

        compose_id = str(uuid.uuid4())
        build_id = self.next_build_id()
        compose = {
            "id": compose_id,
            "koji_build_id": build_id,
        }

        self.composes[compose_id] = {
            "request": js,
            "result": compose,
            "status": "success",
        }

        httpretty.register_uri(
            httpretty.GET,
            self.url + "compose/" + compose_id,
            body=self.compose_status
        )

        return [201, response_headers, json.dumps(compose)]

    def compose_status(self, _request, uri, response_headers):
        target = os.path.basename(uri)
        compose = self.composes.get(target)
        if not compose:
            return [400, response_headers, f"Unknown compose: {target}"]

        ireqs = compose["request"]["image_requests"]
        result = {
            "status": compose["status"],
            "koji_task_id": compose["request"]["koji"]["task_id"],
            "image_statuses": [
                {"status": compose["status"] for _ in ireqs}
            ]
        }
        return [200, response_headers, json.dumps(result)]


@PluginTest.load_plugin("builder")
class TestBuilderPlugin(PluginTest):

    @staticmethod
    def mock_session():
        session = flexmock()

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
            "arches": "x86_64"
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

    def test_plugin_config(self):
        session = flexmock()
        options = self.mock_options()

        composer_url = "https://image-builder.osbuild.org:2323"
        koji_url = "https://koji.osbuild.org/kojihub"
        certs = ["crt", "key"]
        ssl_cert = ", ".join(certs)
        ssl_verify = False
        with tempfile.TemporaryDirectory() as tmp:

            cfg = configparser.ConfigParser()
            cfg["composer"] = {
                "url": composer_url,
                "ssl_cert": ssl_cert,
                "ssl_verify": ssl_verify
            }
            cfg["koji"] = {
                "url": koji_url
            }

            cfgfile = os.path.abspath(os.path.join(tmp, "ko.cfg"))
            with open(cfgfile, 'w') as f:
                cfg.write(f)

            self.plugin.DEFAULT_CONFIG_FILES = [cfgfile]
            handler = self.plugin.OSBuildImage(1,
                                               "osbuildImage",
                                               "params",
                                               session,
                                               options)

            self.assertEqual(handler.composer_url, composer_url)
            self.assertEqual(handler.koji_url, koji_url)
            session = handler.client.http
            self.assertEqual(session.cert, certs)
            self.assertEqual(session.verify, ssl_verify)

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
        session = self.mock_session()
        options = self.mock_options()

        handler = self.plugin.OSBuildImage(1,
                                           "osbuildImage",
                                           "params",
                                           session,
                                           options)

        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["x86_64"],
                {}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["s390x"])
        composer.httpretty_regsiter()

        with self.assertRaises(koji.GenericError):
            handler.handler(*args)

    @httpretty.activate
    def test_compose_success(self):
        # Simulate a successful compose, check return value
        session = self.mock_session()
        options = self.mock_options()

        handler = self.plugin.OSBuildImage(1,
                                           "osbuildImage",
                                           "params",
                                           session,
                                           options)

        repos = ["http://1.repo", "https://2.repo"]
        args = ["name", "version", "distro",
                ["image_type"],
                "fedora-candidate",
                ["x86_64"],
                {"repo": ",".join(repos)}]

        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_regsiter()

        res = handler.handler(*args)
        assert res, "invalid compose result"
        compose_id = res["composer_id"]
        compose = composer.composes.get(compose_id)
        self.assertIsNotNone(compose)

        ireqs = compose["request"]["image_requests"]
        for ir in ireqs:
            self.assertEqual(ir["architecture"], "x86_64")
            have = [r["baseurl"] for r in ir["repositories"]]
            self.assertEqual(have, repos)

    @httpretty.activate
    def test_cli_compose_success(self):
        # Check the basic usage of the plugin as a stand-alone client
        # for the osbuild-composer API
        url = self.plugin.DEFAULT_COMPOSER_URL
        composer = MockComposer(url, architectures=["x86_64"])
        composer.httpretty_regsiter()

        args = [
            "plugins/builder/osbuild.py",
            "compose",
            "Fedora-Cloud-Image",
            "32",
            "20201015.0",
            "fedora-32",
            "http://download.localhost/pub/linux/$arch",
            "x86_64"
        ]

        with unittest.mock.patch.object(sys, 'argv', args):
            res = self.plugin.main()
            self.assertEqual(res, 0)
