# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public API routes, mounted under /api/v1/ before upstream's so they can also override upstream paths."""

from django.urls import path

from plane.oces.urls.initiatives import routes as initiative_routes
from plane.oces.urls.pages import routes as page_routes
from plane.oces.urls.properties import routes

from plane.oces.pql_views import (
    ArchivedWorkItemListAPIEndpoint,
    ProjectWorkItemListAPIEndpoint,
    WorkItemCountAPIEndpoint,
    WorkspaceWorkItemListAPIEndpoint,
)
from plane.oces.type_views import WorkItemTypeDetailAPIEndpoint, WorkItemTypeListCreateAPIEndpoint
from plane.oces.version_views import VersionAPIEndpoint
from plane.oces.views import ProjectFeaturesAPIEndpoint, WorkspaceFeaturesAPIEndpoint

urlpatterns = (
    [
        path("oces/version/", VersionAPIEndpoint.as_view(http_method_names=["get"]), name="oces-v1-version"),
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
        # PQL lists. The project path overrides upstream's GET (POST still creates via upstream code).
        path(
            "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/",
            ProjectWorkItemListAPIEndpoint.as_view(http_method_names=["get", "post"]),
            name="oces-v1-work-items",
        ),
        path(
            "workspaces/<str:slug>/projects/<uuid:project_id>/archived-work-items/",
            ArchivedWorkItemListAPIEndpoint.as_view(http_method_names=["get"]),
            name="oces-v1-archived-work-items",
        ),
        path(
            "workspaces/<str:slug>/work-items/count/",
            WorkItemCountAPIEndpoint.as_view(http_method_names=["get"]),
            name="oces-v1-work-items-count",
        ),
        path(
            "workspaces/<str:slug>/work-items/",
            WorkspaceWorkItemListAPIEndpoint.as_view(http_method_names=["get"]),
            name="oces-v1-workspace-work-items",
        ),
    ]
    + routes(True, "workspaces/<str:slug>", "workspaces/<str:slug>/projects/<uuid:project_id>")
    + initiative_routes(True, "workspaces/<str:slug>")
    + page_routes("workspaces/<str:slug>", "workspaces/<str:slug>/projects/<uuid:project_id>")
)
