#
# koji integration tests
#


import functools
import platform
import unittest
import string
import subprocess


def koji_command(*args, _input=None, _globals=None, **kwargs):
    args = list(args) + [f'--{k}={v}' for k, v in kwargs.items()]
    if _globals:
        args = [f'--{k}={v}' for k, v in _globals.items()] + args
    cmd = ["koji"] + args
    print(cmd)
    return subprocess.run(cmd,
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

    def setUp(self):
        global_args = dict(
            server="http://localhost:8080/kojihub",
            user="kojiadmin",
            password="kojipass",
            authtype="password")
        self.koji = functools.partial(koji_command,
                                      "osbuild-image",
                                      _globals=global_args)

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
