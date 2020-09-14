#
# Test Infrastructure
#


import imp
import os
import unittest


class PluginTest(unittest.TestCase):
    """Base class for Plugin tests

    Use the PluginTest.load_plugin class decorator to automatically
    load a plugin. If said decorator has not been specified, the
    `plugin` property will be set to `None`.
    """

    @staticmethod
    def load_plugin(plugin_type):
        def decorator(klass):
            setattr(klass, "_plugin_type", plugin_type)
            return klass
        return decorator

    def _load_plugin(self):
        plugin_type = getattr(self, "_plugin_type", None)
        if not plugin_type:
            return None

        root = os.getenv("GITHUB_WORKSPACE", os.getcwd())
        haystack = os.path.join(root, "plugins", plugin_type)
        fp, path, desc = imp.find_module("osbuild", [haystack])

        try:
            return imp.load_module("osbuild", fp, path, desc)
        finally:
            fp.close()

    def setUp(self):
        """Setup plugin testing environment

        Will load the specified plugin if the derived class has
        been decorated with `Plugintest.load_plugin()`.
        """
        self.plugin = self._load_plugin()
