# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Internal (web app) routes, mounted under /api/ before upstream's."""

from django.urls import path

from plane.oces.views import ProjectFeaturesEndpoint, WorkspaceFeaturesEndpoint

urlpatterns = [
    path(
        "workspaces/<str:slug>/oces/features/",
        WorkspaceFeaturesEndpoint.as_view(http_method_names=["get", "patch"]),
        name="oces-workspace-features",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/oces/features/",
        ProjectFeaturesEndpoint.as_view(http_method_names=["get", "patch"]),
        name="oces-project-features",
    ),
]
