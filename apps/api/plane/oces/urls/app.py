# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Internal (web app) routes, mounted under /api/ before upstream's."""

from django.urls import path

from plane.oces.urls.initiatives import routes as initiative_routes
from plane.oces.urls.properties import routes
from plane.oces.urls.worklogs import routes as worklog_routes

from plane.oces.board_views import BoardOrderEndpoint
from plane.oces.live import LiveAccessEndpoint
from plane.oces.epic_views import EpicListEndpoint, EpicProgressEndpoint
from plane.oces.type_views import WorkItemTypeDetailEndpoint, WorkItemTypeListCreateEndpoint
from plane.oces.version_views import VersionEndpoint
from plane.oces.views import ProjectFeaturesEndpoint, WorkspaceFeaturesEndpoint

P = "workspaces/<str:slug>/projects/<uuid:project_id>/oces"

urlpatterns = (
    [
        path("oces/version/", VersionEndpoint.as_view(http_method_names=["get"]), name="oces-version"),
        path(
            "workspaces/<str:slug>/oces/live-access/",
            LiveAccessEndpoint.as_view(http_method_names=["get"]),
            name="oces-live-access",
        ),
        path(
            "workspaces/<str:slug>/oces/features/",
            WorkspaceFeaturesEndpoint.as_view(http_method_names=["get", "patch"]),
            name="oces-workspace-features",
        ),
        path(
            f"{P}/features/",
            ProjectFeaturesEndpoint.as_view(http_method_names=["get", "patch"]),
            name="oces-project-features",
        ),
        path(
            f"{P}/work-item-types/",
            WorkItemTypeListCreateEndpoint.as_view(http_method_names=["get", "post"]),
            name="oces-work-item-types",
        ),
        path(
            f"{P}/work-item-types/<uuid:type_id>/",
            WorkItemTypeDetailEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
            name="oces-work-item-type",
        ),
        path(f"{P}/epics/", EpicListEndpoint.as_view(http_method_names=["get"]), name="oces-epics"),
        path(
            f"{P}/board-order/",
            BoardOrderEndpoint.as_view(http_method_names=["get", "put"]),
            name="oces-board-order",
        ),
        path(
            f"{P}/epics/<uuid:epic_id>/progress/",
            EpicProgressEndpoint.as_view(http_method_names=["get"]),
            name="oces-epic-progress",
        ),
    ]
    + routes(False, "workspaces/<str:slug>/oces", P)
    + initiative_routes(False, "workspaces/<str:slug>/oces")
    + worklog_routes(False, P)
)
