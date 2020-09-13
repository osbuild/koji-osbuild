#
# koji hub plugin unit tests
#


import unittest
import os
import imp
from flexmock import flexmock


class TestHubPlugin(unittest.TestCase):
    def setUp(self):
        """Loads the plugin to self.plugin"""
        root = os.getenv("GITHUB_WORKSPACE", os.getcwd())

        haystack = os.path.join(root, "plugins", "hub")

        fp, path, desc = imp.find_module("osbuild", [haystack])
        try:
            self.plugin = imp.load_module("osbuild", fp, path, desc)
        finally:
            fp.close()

    @staticmethod
    def mock_koji_context(*, admin=False):
        session = flexmock()
        session.should_receive("hasPerm") \
               .with_args("admin") \
               .and_return(admin)

        session.should_receive("assertPerm") \
               .with_args("image") \
               .once()

        context = flexmock(session=session)
        return context

    @staticmethod
    def mock_kojihub(args, task):
        kojihub = flexmock()
        kojihub.should_receive("make_task") \
               .with_args("osbuildImage", args, **task)
        return kojihub

    def test_basic(self):
        context = self.mock_koji_context()

        opts = {}
        args = ["name", "version", "distro",
                ["image_type"],
                "target",
                ["arches"],
                opts]

        task = {"channel": "image"}

        kojihub = self.mock_kojihub(args, task)

        setattr(self.plugin, "context", context)
        setattr(self.plugin, "kojihub", kojihub)

        self.plugin.osbuildImage(*args, opts)
