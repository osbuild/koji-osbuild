#
# koji integration tests
#


import functools
import unittest
import subprocess


F32_REPO = "http://download.fedoraproject.org/pub/fedora/linux/releases/32/Everything/$arch/os"


def koji_command(*args, _input=None, _globals=None, **kwargs):
    args = list(args) + [f'--{k}={v}' for k, v in kwargs.items()]
    if _globals:
        args = [f'--{k}={v}' for k, v in _globals.items()] + args
    return subprocess.run(["koji"] + args,
                          encoding="utf-8",
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          input=_input,
                          check=False)


class TestIntegration(unittest.TestCase):

    def setUp(self):
        global_args = dict(
            server="http://localhost/kojihub",
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
        # Simple test of a successful compose of F32
        # Needs the f32-candidate tag be setup properly
        res = self.koji("Fedora-Cloud",
                        "32",
                        "fedora-32",
                        "f32-candidate",
                        "x86_64",
                        repo=F32_REPO)
        self.check_res(res)

    def test_unknown_tag_check(self):
        """Unknown Tag check"""
        # Check building an unknown tag fails
        res = self.koji("Fedora-Cloud",
                        "32",
                        "fedora-32",
                        "UNKNOWNTAG",
                        "x86_64")
        self.check_fail(res)
