#
# koji hub plugin unit tests
#

import jsonschema
import koji
from flexmock import flexmock

from plugintest import PluginTest


@PluginTest.load_plugin("hub")
class TestHubPlugin(PluginTest):

    @staticmethod
    def mock_koji_context(*, times=1, admin=False):
        session = flexmock()
        session.should_receive("hasPerm") \
               .with_args("admin") \
               .and_return(admin)

        session.should_receive("assertPerm") \
               .with_args("image") \
               .times(times)

        context = flexmock(session=session)
        return context

    @staticmethod
    def mock_kojihub(args, task):
        kojihub = flexmock()
        kojihub.should_receive("make_task") \
               .with_args("osbuildImage", args, **task)
        return kojihub

    def test_plugin_jsonschema(self):
        # Make sure the schema used to validate the input is
        # itself correct jsonschema
        schema = self.plugin.OSBUILD_IMAGE_SCHEMA
        jsonschema.Draft4Validator.check_schema(schema)

    def test_basic(self):
        context = self.mock_koji_context()

        opts = {
            "repo": ["repo1", "repo2"],
            "release": "1.2.3",
            "skip_tag": True
        }
        args = [
            "name",
            "version",
            "distro",
            "image_type",
            "target",
            ["arches"]
        ]
        make_task_args = args + [opts]
        task = {"channel": "image"}

        kojihub = self.mock_kojihub(make_task_args, task)

        setattr(self.plugin, "context", context)
        setattr(self.plugin, "kojihub", kojihub)

        self.plugin.osbuildImage(*args, opts)

    def test_image_types_array(self):
        context = self.mock_koji_context()

        opts = {
            "repo": ["repo1", "repo2"],
            "release": "1.2.3",
            "skip_tag": True
        }
        args = [
            "name",
            "version",
            "distro",
            ["image_type"],
            "target",
            ["arches"]
        ]
        make_task_args = [
            "name",
            "version",
            "distro",
            "image_type",
            "target",
            ["arches"]
        ] + [opts]
        task = {"channel": "image"}

        kojihub = self.mock_kojihub(make_task_args, task)

        setattr(self.plugin, "context", context)
        setattr(self.plugin, "kojihub", kojihub)

        self.plugin.osbuildImage(*args, opts)

    def test_input_validation(self):
        test_cases = [
            # only a single image type is allowed
            {
                "args": [
                    "name",
                    "version",
                    "distro",
                    ["image_type", "image_type2"],
                    "target",
                    ["arches"]
                ],
                "opts": {}
            },
            # repo without `baseurl` is not allowed
            {
                "args": [
                    "name",
                    "version",
                    "distro",
                    "image_type",
                    "target",
                    ["arches"]
                ],
                "opts": {
                    "repo": [
                        {
                            "package_sets": ["set1", "set2"]
                        }
                    ]
                }
            }
        ]

        context = self.mock_koji_context(times=len(test_cases))
        setattr(self.plugin, "context", context)

        for idx, test_case in enumerate(test_cases):
            with self.subTest(idx=idx):
                with self.assertRaises(koji.ParameterError):
                    self.plugin.osbuildImage(*test_case["args"], test_case["opts"])
