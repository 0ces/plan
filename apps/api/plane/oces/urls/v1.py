# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public API routes, mounted under /api/v1/ before upstream's so they can also override upstream paths."""

from django.urls import path

from plane.oces.type_views import WorkItemTypeDetailAPIEndpoint, WorkItemTypeListCreateAPIEndpoint
from plane.oces.views import ProjectFeaturesAPIEndpoint, WorkspaceFeaturesAPIEndpoint

urlpatterns = [
    path(
        "workspaces/<str:slug>/features/",
        WorkspaceFeaturesAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="oces-v1-workspace-features",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/features/",
        ProjectFeaturesAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="oces-v1-project-features",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        WorkItemTypeListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="oces-v1-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/",
        WorkItemTypeDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="oces-v1-work-item-type",
    ),
]
