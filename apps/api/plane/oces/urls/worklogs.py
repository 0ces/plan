# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Time log routes for the public API and, under the `oces/` prefix, the web app."""

from django.urls import path

from plane.oces import worklog_views as v


def routes(public, proj):
    s = "APIEndpoint" if public else "Endpoint"
    view = lambda name, methods: getattr(v, name + s).as_view(http_method_names=methods)  # noqa: E731
    tag = "oces-v1" if public else "oces"
    w = f"{proj}/work-items/<uuid:work_item_id>/worklogs"
    return [
        path(f"{w}/", view("WorkLogList", ["get", "post"]), name=f"{tag}-work-logs"),
        path(f"{w}/<uuid:work_log_id>/", view("WorkLogDetail", ["get", "patch", "delete"]), name=f"{tag}-work-log"),
        path(f"{proj}/worklogs/summary/", view("WorkLogSummary", ["get"]), name=f"{tag}-work-log-summary"),
        path(f"{proj}/worklogs/", view("ProjectWorkLogs", ["get"]), name=f"{tag}-project-work-logs"),
    ]
