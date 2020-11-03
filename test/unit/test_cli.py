#
# koji command line interface plugin unit tests
#


import contextlib
import io
import koji
import koji_cli.lib as kl
from flexmock import flexmock

from plugintest import PluginTest


@PluginTest.load_plugin("cli")
class TestCliPlugin(PluginTest):

    @staticmethod
    def mock_koji_lib(*, bg=False, task_result=0):
        kojilib = flexmock(OptionParser=kl.OptionParser)

        kojilib.should_receive("get_usage_str").and_return("usage")
        kojilib.should_receive("activate_session").once()
        kojilib.should_receive("_running_in_bg").and_return(bg)
        kojilib.should_receive("watch_tasks").and_return(task_result)

        return kojilib

    @staticmethod
    def mock_options(*, quiet=False):
        options = flexmock(
            quiet=quiet,
            weburl="http://osbuild.org/"
        )
        return options


    @staticmethod
    def mock_session_add_valid_tag(session):
        build_target = {
            "build_tag": 23,
            "build_tag_name": "target-build",
            "dest_tag": 42,
            "dest_tag_name": "target-dest"
        }

        tag_info = {
            "id": build_target["dest_tag"],
            "name": build_target["dest_tag_name"],
            "locked": False
        }

        session.should_receive("getBuildTarget") \
               .with_args("target") \
               .and_return(build_target) \
               .once()

        session.should_receive("getTag") \
               .with_args(build_target["dest_tag"]) \
               .and_return(tag_info) \
               .once()

        return session

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

        # check one successful invocation
        argv = ["name", "version", "distro", "target", "arch1"]

        expected_args = ["name", "version", "distro",
                         ['qcow2'], # the default image type
                         "target",
                         ['arch1']]

        expected_opts = {}

        task_result = {"compose_id": "42", "build_id": 23}
        task_id = 1
        koji_lib = self.mock_koji_lib()

        options = self.mock_options()
        session = flexmock()

        self.mock_session_add_valid_tag(session)

        session.should_receive("osbuildImage") \
               .with_args(*expected_args, opts=expected_opts) \
               .and_return(task_id) \
               .once()

        session.should_receive("logout") \
               .with_args() \
               .once()

        session.should_receive("getTaskResult") \
               .with_args(task_id) \
               .and_return(task_result) \
               .once()

        setattr(self.plugin, "kl", koji_lib)
        r = self.plugin.handle_osbuild_image(options, session, argv)
        self.assertEqual(r, 0)

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
