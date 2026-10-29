# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public API routes, mounted under /api/v1/ before upstream's so they can also override upstream paths."""

from django.urls import path

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
]
