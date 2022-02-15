#
# koji integration tests
#


import functools
import platform
import unittest
import string
import subprocess


REPOS = {
    "fedora": [
        "http://download.fedoraproject.org/pub/fedora/linux/releases/$release/Everything/$arch/os"
    ],
    "rhel": [
        "http://download.devel.redhat.com/released/RHEL-8/$release/BaseOS/x86_64/os/",
        "http://download.devel.redhat.com/released/RHEL-8/$release/AppStream/x86_64/os/",
    ]
}


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


def parse_os_release():
    info = {}
    with open("/etc/os-release") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line[0] == "#":
                continue
            k, v = line.split("=", 1)
            info[k] = v.strip('"')
    return info


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

        info = parse_os_release()

        name = info["ID"]  # 'fedora' or 'rhel'
        version = info["VERSION_ID"]  # <major> or <major>.<minor>

        comps = version.split(".")
        major = comps[0]
        minor = comps[1] if len(comps) > 1 else ""

        distro = f"{name}-{major}{minor}"
        tag = f"{name}{major}-candidate"  # fedora<major> or rhel<major>
        arch = platform.machine()

        release = version
        if name.lower() == "rhel":
            release += ".0"

        repos = []
        for repo in REPOS[name]:
            tpl = string.Template(repo)
            url = tpl.safe_substitute({"release": release})
            repos += ["--repo", url]

        package = f"{name.lower()}-guest"

        res = self.koji(package,
                        major,
                        distro,
                        tag,
                        arch,
                        "--wait",
                        *repos)
        self.check_res(res)

    def test_unknown_tag_check(self):
        """Unknown Tag check"""
        # Check building an unknown tag fails

        info = parse_os_release()

        name = info["ID"]  # 'fedora' or 'rhel'
        version = info["VERSION_ID"]  # <major> or <major>.<minor>
        major = version.split(".")[0]
        distro = f"{name}-{major}"

        res = self.koji("fedora-guest",
                        major,
                        distro,
                        "UNKNOWNTAG",
                        platform.machine())
        self.check_fail(res)
