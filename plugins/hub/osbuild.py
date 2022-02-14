"""Koji osbuild integration for Koji Hub"""
import sys
import jsonschema

import koji
from koji.context import context

sys.path.insert(0, "/usr/share/koji-hub/")
import kojihub  # pylint: disable=import-error, wrong-import-position


OSBUILD_IMAGE_SCHEMA = {
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
            "minItems": 1,
            "items": {
                "type": "string"
            }
        },
        {
            "type": "object",
            "$ref": "#/definitions/options"
        }],
    "definitions": {
        "ostree": {
            "title": "OSTree specific options",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "parent": {
                    "type": "string"
                },
                "ref": {
                    "type": "string"
                },
                "url": {
                    "type": "string"
                }
            }
        },
        "options": {
            "title": "Optional arguments",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ostree": {
                    "type": "object",
                    "$ref": "#/definitions/ostree"
                },
                "repo": {
                    "type": "array",
                    "description": "Repositories",
                    "items": {
                        "type": "string"
                    }
                },
                "release": {
                    "type": "string",
                    "description": "Release override"
                },
                "skip_tag": {
                    "type": "boolean",
                    "description": "Omit tagging the result"
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

    try:
        jsonschema.validate(args, OSBUILD_IMAGE_SCHEMA)
    except jsonschema.exceptions.ValidationError as err:
        raise koji.ParameterError(str(err)) from None

    if priority and priority < 0 and not context.session.hasPerm('admin'):
        raise koji.ActionNotAllowed('only admins may create high-priority tasks')

    return kojihub.make_task('osbuildImage', args, **task)
