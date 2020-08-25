#!/usr/bin/python3
import koji
import os

base = "container/ssl/kojiadmin"
cert = os.path.join(base, "client.pem")
serverca = os.path.join(base, "serverca.crt")

session = koji.ClientSession("http://localhost:8081/kojihub", {})
session.ssl_login(cert, None, serverca)
session.osbuildImageTest("fedora", "32", ["x86_64"], "f32")
