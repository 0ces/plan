# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Initiative routes for the public API and, under `oces/`, the web app."""

from django.urls import path

from plane.oces import initiative_views as v


def routes(public, ws):
    s = "APIEndpoint" if public else "Endpoint"
    tag = "oces-v1" if public else "oces"
    i = f"{ws}/initiatives"
    one = f"{i}/<uuid:initiative_id>"

    def view(name, methods):
        return getattr(v, name + s).as_view(http_method_names=methods)

    return [
        path(f"{i}/labels/", view("LabelList", ["get", "post"]), name=f"{tag}-initiative-labels"),
        path(
            f"{i}/labels/<uuid:label_id>/",
            view("LabelDetail", ["get", "patch", "delete"]),
            name=f"{tag}-initiative-label",
        ),
        path(f"{i}/", view("InitiativeList", ["get", "post"]), name=f"{tag}-initiatives"),
        path(f"{one}/", view("InitiativeDetail", ["get", "patch", "delete"]), name=f"{tag}-initiative"),
        path(
            f"{one}/projects/", view("InitiativeProjects", ["get", "post", "delete"]), name=f"{tag}-initiative-projects"
        ),
        path(f"{one}/work-items/", view("InitiativeItems", ["get", "post", "delete"]), name=f"{tag}-initiative-items"),
        path(f"{one}/epics/", view("InitiativeEpics", ["get", "post", "delete"]), name=f"{tag}-initiative-epics"),
        path(
            f"{one}/labels/", view("InitiativeLabels", ["get", "post", "delete"]), name=f"{tag}-initiative-label-links"
        ),
    ]
