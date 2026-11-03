# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Page routes for the public API (the paths the official SDK uses)."""

from django.urls import path

from plane.oces import page_views as v


def routes(ws, proj):
    def scoped(prefix, scope):
        one = f"{prefix}/pages/<uuid:page_id>"
        return [
            path(
                f"{prefix}/pages/", getattr(v, f"{scope}PageListAPIEndpoint").as_view(), name=f"oces-v1-{scope}-pages"
            ),
            path(f"{one}/", getattr(v, f"{scope}PageDetailAPIEndpoint").as_view(), name=f"oces-v1-{scope}-page"),
            path(
                f"{one}/archive/",
                getattr(v, f"{scope}PageArchiveAPIEndpoint").as_view(),
                name=f"oces-v1-{scope}-page-archive",
            ),
        ]

    item = f"{proj}/work-items/<uuid:issue_id>/pages"
    return (
        scoped(ws, "Workspace")
        + scoped(proj, "Project")
        + [
            path(f"{item}/", v.WorkItemPageListAPIEndpoint.as_view(), name="oces-v1-work-item-pages"),
            path(f"{item}/<uuid:link_id>/", v.WorkItemPageDetailAPIEndpoint.as_view(), name="oces-v1-work-item-page"),
        ]
    )
