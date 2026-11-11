# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public API relation routes the Plane MCP calls (see plane/oces/relation_views.py)."""

from django.urls import path, re_path

from plane.oces import relation_views as v


def routes(ws, proj):
    w = f"{proj}/work-items/<uuid:issue_id>"
    return [
        path(
            f"{w}/dependencies/",
            v.WorkItemDependenciesAPIEndpoint.as_view(http_method_names=["get", "post"]),
            name="oces-v1-work-item-dependencies",
        ),
        path(
            f"{w}/dependencies/<uuid:related_id>/",
            v.WorkItemDependencyDetailAPIEndpoint.as_view(http_method_names=["delete"]),
            name="oces-v1-work-item-dependency",
        ),
        path(
            f"{w}/work-item-relations/",
            v.WorkItemCustomRelationsAPIEndpoint.as_view(http_method_names=["get"]),
            name="oces-v1-work-item-custom-relations",
        ),
        path(
            f"{w}/work-item-relations/<uuid:related_id>/",
            v.WorkItemCustomRelationDetailAPIEndpoint.as_view(http_method_names=["delete"]),
            name="oces-v1-work-item-custom-relation",
        ),
        # the SDK posts here without a trailing slash
        re_path(
            r"^workspaces/(?P<slug>[^/]+)/projects/(?P<project_id>[0-9a-f-]{36})/work-items/"
            r"(?P<issue_id>[0-9a-f-]{36})/relations/remove/?$",
            v.WorkItemRelationRemoveAPIEndpoint.as_view(http_method_names=["post"]),
            name="oces-v1-work-item-relation-remove",
        ),
        path(
            f"{ws}/work-item-relation-definitions/",
            v.RelationDefinitionsAPIEndpoint.as_view(http_method_names=["get"]),
            name="oces-v1-relation-definitions",
        ),
    ]
