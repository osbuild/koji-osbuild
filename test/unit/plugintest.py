#
# Test Infrastructure
#


import importlib
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
        haystack = os.path.join(root, "plugins", plugin_type, "osbuild.py")
        spec = importlib.util.spec_from_file_location("osbuild", haystack)
        assert spec, f"Could not find '{plugin_type}' plugin"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setUp(self):
        """Setup plugin testing environment

        Will load the specified plugin if the derived class has
        been decorated with `Plugintest.load_plugin()`.
        """
        self.plugin = self._load_plugin()
