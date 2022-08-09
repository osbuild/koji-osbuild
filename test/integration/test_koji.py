#
# koji integration tests
#


import functools
import json
import logging
import os
import platform
import re
import shutil
import string
import subprocess
import tempfile
import unittest

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError as BotoClientError


logger = logging.getLogger(__name__)
logging.basicConfig(format = '%(asctime)s %(levelname)s: %(message)s', level = logging.INFO)


def koji_command(*args, _input=None, _globals=None, **kwargs):
    return koji_command_cwd(*args, _input=_input, _globals=_globals, **kwargs)


def koji_command_cwd(*args, cwd=None, _input=None, _globals=None, **kwargs):
    args = list(args) + [f'--{k}={v}' for k, v in kwargs.items()]
    if _globals:
        args = [f'--{k}={v}' for k, v in _globals.items()] + args
    cmd = ["koji"] + args
    logger.info("Running %s", str(cmd))
    return subprocess.run(cmd,
                          cwd=cwd,
                          encoding="utf-8",
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          input=_input,
                          check=False)


class SutInfo:
    """Class representing information about the system under test"""

    REPOS = {
        "fedora": [
            {"url": "http://download.fedoraproject.org/pub/fedora/linux/releases/$release/Everything/$arch/os"}
        ],
        "rhel": [
            {"url": "http://download.devel.redhat.com/released/RHEL-8/$release/BaseOS/$arch/os/",
            "package_sets": "blueprint; build; packages"},
            {"url": "http://download.devel.redhat.com/released/RHEL-8/$release/AppStream/$arch/os/",
            "package_sets": "blueprint; build; packages"},
        ]
    }

    def __init__(self):
        info = SutInfo.parse_os_release()

        self.os_name = info["ID"]  # 'fedora' or 'rhel'
        self.os_version = info["VERSION_ID"]  # <major> or <major>.<minor>

        comps = self.os_version.split(".")
        self.os_version_major = comps[0]
        self.os_version_minor = comps[1] if len(comps) > 1 else ""

        self.composer_distro_name = f"{self.os_name}-{self.os_version_major}{self.os_version_minor}"
        self.koji_tag = f"{self.os_name}{self.os_version_major}-candidate"  # fedora<major> or rhel<major>
        self.os_arch = platform.machine()

    @staticmethod
    def parse_os_release():
        info = {}
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line[0] == "#":
                    continue
                k, v = line.split("=", 1)
                info[k] = v.strip('"')
        return info

    def testing_repos(self):
        """
        Returns a list of repositories to be used by the test.

        All variables in the URLs are replaced by proper values.
        """
        release = self.os_version
        if self.os_name.lower() == "rhel":
            release += ".0"

        repos = []
        for repo in self.REPOS[self.os_name]:
            repo_copy = dict(repo)
            tpl = string.Template(repo_copy["url"])
            url = tpl.safe_substitute({
                "release": release,
                "arch": self.os_arch,
            })
            repo_copy["url"] = url
            repos.append(repo_copy)

        return repos


class TestIntegration(unittest.TestCase):
    logger = logging.getLogger(__name__)

    def setUp(self):
        self.koji_global_args = dict(
            server="http://localhost:8080/kojihub",
            topurl="http://localhost:8080/kojifiles",
            user="kojiadmin",
            password="kojipass",
            authtype="password")
        self.koji = functools.partial(koji_command,
                                      "osbuild-image",
                                      _globals=self.koji_global_args)

        self.workdir = tempfile.mkdtemp()
        # EC2 image ID to clean up in tearDown() if set to a value
        self.ec2_image_id = None

    def tearDown(self):
        shutil.rmtree(self.workdir)
        if self.ec2_image_id is not None:
            self.delete_ec2_image(self.ec2_image_id)
            self.ec2_image_id = None

    def check_res(self, res: subprocess.CompletedProcess):
        if res.returncode != 0:
            msg = ("\nkoji FAILED:" +
                   "\n args: [" + " ".join(res.args) + "]" +
                   "\n error: " + res.stdout)
            self.fail(msg)

    def check_fail(self, res: subprocess.CompletedProcess):
        if res.returncode == 0:
            msg = ("\nkoji unexpectedly succeed:" +
                   "\n args: [" + " ".join(res.args) + "]" +
                   "\n error: " + res.stdout)
            self.fail(msg)

    def task_id_from_res(self, res: subprocess.CompletedProcess) -> str:
        """
        Extract the Task ID from `koji osbuild-image` command output and return it.
        """
        r = re.compile(r'^Created task:[ \t]+(\d+)$', re.MULTILINE)
        m = r.search(res.stdout)
        if not m:
            self.fail("Could not find task id in output")
        return m.group(1)

    @staticmethod
    def get_ec2_client():
        aws_region = os.getenv("AWS_REGION")
        return boto3.client('ec2', config=BotoConfig(region_name=aws_region))

    def check_ec2_image_exists(self, image_id: str) -> None:
        """
        Check if an EC2 image with the given ID exists.
        If not, fail the test case.
        """
        client = self.get_ec2_client()
        try:
            resp = client.describe_images(ImageIds=[image_id])
        except BotoClientError as e:
            self.fail(str(e))
        self.assertEqual(len(resp["Images"]), 1)

    def delete_ec2_image(self, image_id: str) -> None:
        client = self.get_ec2_client()
        # first get the snapshot ID associated with the image
        try:
            resp = client.describe_images(ImageIds=[image_id])
        except BotoClientError as e:
            self.fail(str(e))
        self.assertEqual(len(resp["Images"]), 1)

        snapshot_id = resp["Images"][0]["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]
        # deregister the image
        try:
            resp = client.deregister_image(ImageId=image_id)
        except BotoClientError as e:
            self.logger.warning("Failed to deregister image %s: %s", image_id, str(e))

        # delete the associated snapshot
        try:
            resp = client.delete_snapshot(SnapshotId=snapshot_id)
        except BotoClientError as e:
            self.logger.warning("Failed to delete snapshot %s: %s", snapshot_id, str(e))

    def test_compose(self):
        """Successful compose"""
        # Simple test of a successful compose of RHEL

        sut_info = SutInfo()

        repos = []
        for repo in sut_info.testing_repos():
            url = repo["url"]
            package_sets = repo.get("package_sets")
            repos += ["--repo", url]
            if package_sets:
                repos += ["--repo-package-sets", package_sets]

        package = f"{sut_info.os_name.lower()}-guest"

        res = self.koji(package,
                        sut_info.os_version_major,
                        sut_info.composer_distro_name,
                        sut_info.koji_tag,
                        sut_info.os_arch,
                        "--wait",
                        *repos)
        self.check_res(res)

    def test_unknown_tag_check(self):
        """Unknown Tag check"""
        # Check building an unknown tag fails

        sut_info = SutInfo()
        package = f"{sut_info.os_name.lower()}-guest"

        res = self.koji(package,
                        sut_info.os_version_major,
                        sut_info.composer_distro_name,
                        "UNKNOWNTAG",
                        sut_info.os_arch)
        self.check_fail(res)

    def test_cloud_upload_aws(self):
        """Successful compose with cloud upload to AWS"""
        sut_info = SutInfo()

        repos = []
        for repo in sut_info.testing_repos():
            url = repo["url"]
            package_sets = repo.get("package_sets")
            repos += ["--repo", url]
            if package_sets:
                repos += ["--repo-package-sets", package_sets]

        package = "aws"
        aws_region = os.getenv("AWS_REGION")

        upload_options = {
            "region": aws_region,
            "share_with_accounts": [os.getenv("AWS_API_TEST_SHARE_ACCOUNT")]
        }

        upload_options_file = os.path.join(self.workdir, "upload_options.json")
        with open(upload_options_file, "w", encoding="utf-8") as f:
            json.dump(upload_options, f)

        res = self.koji(package,
                        sut_info.os_version_major,
                        sut_info.composer_distro_name,
                        sut_info.koji_tag,
                        sut_info.os_arch,
                        "--wait",
                        *repos,
                        f"--image-type={package}",
                        f"--upload-options={upload_options_file}")
        self.check_res(res)

        task_id = self.task_id_from_res(res)
        # Download files uploaded by osbuild plugins to the Koji build task.
        # requires koji client of version >= 1.29.1
        res_download = koji_command_cwd(
            "download-task", "--all", task_id, cwd=self.workdir, _globals=self.koji_global_args
        )
        self.check_res(res_download)

        # Extract information about the uploaded AMI from compose status response.
        compose_status_file = os.path.join(self.workdir, "compose-status.noarch.json")
        with open(compose_status_file, "r", encoding="utf-8") as f:
            compose_status = json.load(f)

        self.assertEqual(compose_status["status"], "success")
        image_statuses = compose_status["image_statuses"]
        self.assertEqual(len(image_statuses), 1)

        upload_status = image_statuses[0]["upload_status"]
        self.assertEqual(upload_status["status"], "success")
        self.assertEqual(upload_status["type"], "aws")

        upload_options = upload_status["options"]
        self.assertEqual(upload_options["region"], aws_region)

        image_id = upload_options["ami"]
        self.assertNotEqual(len(image_id), 0)
        self.ec2_image_id = image_id
        self.check_ec2_image_exists(image_id)
