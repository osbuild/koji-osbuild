#
# koji command line interface plugin unit tests
#


import contextlib
import io
import koji
from flexmock import flexmock

from plugintest import PluginTest


@PluginTest.load_plugin("cli")
class TestCliPlugin(PluginTest):

    def test_basic_invocation(self):
        # check we get the right amount of arguments
        # i.e. we are missing the architecture here
        argv = ["name", "version", "distro", "target"]

        f = io.StringIO()
        with self.assertRaises(SystemExit) as cm, \
             contextlib.redirect_stderr(f):
            self.plugin.handle_osbuild_image(None, None, argv)
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("osbuild-image", f.getvalue())
        f.close()

    def test_target_check(self):
        # unknown build target
        session = flexmock()

        session.should_receive("getBuildTarget") \
               .with_args("target") \
               .and_return(None) \
               .once()

        argv = ["name", "version", "distro", "target", "arch1"]
        with self.assertRaises(koji.GenericError):
            self.plugin.handle_osbuild_image(None, session, argv)

        # unknown destination tag
        build_target = {
            "build_tag": 23,
            "build_tag_name": "target-build",
            "dest_tag": 42,
            "dest_tag_name": "target-dest"  # missing!
        }

        session = flexmock()

        session.should_receive("getBuildTarget") \
               .with_args("target") \
               .and_return(build_target) \
               .once()

        session.should_receive("getTag") \
               .with_args(build_target["dest_tag"]) \
               .and_return(None) \
               .once()

        argv = ["name", "version", "distro", "target", "arch1"]
        with self.assertRaises(koji.GenericError):
            self.plugin.handle_osbuild_image(None, session, argv)
