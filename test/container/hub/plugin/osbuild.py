import koji

from koji.tasks import BaseTaskHandler


class OSBuildImage(BaseTaskHandler):
    Methods = ['osbuildImage']
    _taskWeight = 2.0

    def handler(self, name, version, arches, target, opts):
        self.logger.debug("Building image %s, %s, %s, %s",
                          name, str(arches), str(target), str(opts))

        #self.logger.debug("Event id: %s", str(self.event_id))

        target_info = self.session.getBuildTarget(target, strict=True)
        build_tag = target_info['build_tag']
        repo_info = self.getRepo(build_tag)
        buildconfig = self.session.getBuildConfig(build_tag)

        if repo_info:
            self.logger.debug("repo info: %s", str(repo_info))

        if buildconfig:
            self.logger.debug("build-config: %s", str(buildconfig))

        return {
            'repositories': [],
            'koji_builds': [],
            'build': 'skipped',
        }
