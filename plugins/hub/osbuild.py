import sys

import logging
import koji
from koji.context import context

sys.path.insert(0, "/usr/share/koji-hub/")
import kojihub


@koji.plugin.export
def osbuildImage(name, version, arches, target, opts=None, priority=None):
    """Create an image via osbuild"""
    context.session.assertPerm("image")
    args = [name, version, arches, target, opts]
    task = {"channel": "image"}

    if priority and priority < 0 and not context.session.hasPerm('admin'):
        raise koji.ActionNotAllowed('only admins may create high-priority tasks')

    return kojihub.make_task('osbuildImage', args, **task)
