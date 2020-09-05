
import urllib.request
import json
import sys
import time

import koji

from koji.tasks import BaseTaskHandler


def compose_request(distro, koji):
    req = {
        "distribution": distro,
        "koji": {
            "server": koji
        },
        "image_requests": [{
            "architecture": "x86_64",
            "image_type": "qcow2",
            "repositories": [{
                "baseurl": "http://download.fedoraproject.org/pub/fedora/linux/releases/32/Everything/x86_64/os/"
            }]
        }]
    }

    return req


class OSBuildImage(BaseTaskHandler):
    Methods = ['osbuildImage']
    _taskWeight = 2.0

    def handler(self, name, version, arches, target, opts):
        self.logger.debug("Building image %s, %s, %s, %s",
                          name, str(arches), str(target), str(opts))

        #self.logger.debug("Event id: %s", str(self.event_id))

        #target_info = self.session.getBuildTarget(target, strict=True)
        #build_tag = target_info['build_tag']
        #repo_info = self.getRepo(build_tag)
        #buildconfig = self.session.getBuildConfig(build_tag)

        #if repo_info:
        #    self.logger.debug("repo info: %s", str(repo_info))

        #if buildconfig:
        #    self.logger.debug("build-config: %s", str(buildconfig))

        # <<<>>>

        cr = compose_request("fedora-32", "https://localhost/kojihub")
        data = json.dumps(cr)

        req = urllib.request.Request("http://composer:8701/compose")
        req.add_header('Content-Type', 'application/json')
        raw = data.encode('utf-8')
        req.add_header('Content-Length', len(raw))
        with urllib.request.urlopen(req, raw) as res:
            payload = res.read().decode('utf-8')
            if res.status != 201:
                self.logger.debug("Failed to create compose: %s", str(payload))
                return {
                    'repositories': [],
                    'koji_builds': [],
                    'build': 'skipped',
                }
            ps = json.loads(payload)
            compose_id = ps["id"]

        req = urllib.request.Request(f"http://composer:8701/compose/{compose_id}")
        while True:
            with urllib.request.urlopen(req) as res:
                payload = res.read().decode('utf-8')
                if res.status != 200:
                    self.logger.debug("Failed to get compose status: %s", str(payload))
                    return {
                        'repositories': [],
                        'koji_builds': [],
                        'build': 'skipped',
                    }

            ps = json.loads(payload)
            status = ps["status"]
            self.logger.debug("Compose status: %s", status)
            if status != "RUNNING" and status != "WAITING":
                break
            time.sleep(2)

        if status == "FAILED":
            self.logger.debug("Compose failed: %s", str(payload))
            return {
                'repositories': [],
                'koji_builds': [],
                'build': 'skipped',
            }

        return {
            'repositories': [],
            'koji_builds': [],
            'build': f'{compose_id}-1',
        }
