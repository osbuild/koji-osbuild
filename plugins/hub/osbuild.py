"""Koji osbuild integration for Koji Hub"""
import sys

import jsonschema

import logging
import koji
from koji.context import context

sys.path.insert(0, "/usr/share/koji-hub/")
import kojihub


OSBUILD_IMAGE_SCHMEA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "osbuildImage arguments",
    "type": "array",
    "minItems": 7,
    "items": [
        {
            "type": "string",
            "description": "Name"
        },
        {
            "type": "string",
            "description": "Version"
        },
        {
            "type": "string",
            "description": "Distribution"
        },
        {
            "type": "array",
            "description": "Image Types",
            "minItems": 1
        },
        {
            "type": "string",
            "description": "Target"
        },
        {
            "type": "array",
            "description": "Architectures",
            "minItems": 1
        },
        {
            "type": "object",
            "$ref": "#/definitions/options"
        }],
    "definitions": {
        "options":{
            "title": "Optional arguments",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repositories"
                },
                "release": {
                    "type": "string",
                    "description": "Release override"
                }
            }
        }
    }
}


@koji.plugin.export
def osbuildImage(name, version, distro, image_types, target, arches, opts=None, priority=None):
    """Create an image via osbuild"""
    context.session.assertPerm("image")
    args = [name, version, distro, image_types, target, arches, opts]
    task = {"channel": "image"}

    jsonschema.validate(args, OSBUILD_IMAGE_SCHMEA)

    if priority and priority < 0 and not context.session.hasPerm('admin'):
        raise koji.ActionNotAllowed('only admins may create high-priority tasks')

    return kojihub.make_task('osbuildImage', args, **task)
