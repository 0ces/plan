# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Property routes. The same paths serve the public API (/api/v1/workspaces/...) and,
under an `oces/` prefix, the web app (/api/workspaces/...)."""

from django.urls import path

from plane.oces import module_property_views as mv
from plane.oces import property_views as v

ALL = ["get", "post", "patch", "delete"]


def routes(public, ws, proj):
    """ws/proj are the path prefixes; public picks the X-Api-Key or session views."""
    s = "APIEndpoint" if public else "Endpoint"
    view = lambda name, methods: getattr(v, name + s).as_view(http_method_names=methods)  # noqa: E731
    tag = "oces-v1" if public else "oces"
    t = f"{proj}/work-item-types/<uuid:type_id>"
    out = [
        path(f"{t}/work-item-properties/", view("TypePropertyList", ["get", "post"]), name=f"{tag}-type-properties"),
        path(
            f"{t}/work-item-properties/<uuid:property_id>/",
            view("TypePropertyDetail", ["get", "patch", "delete"]),
            name=f"{tag}-type-property",
        ),
        path(f"{t}/properties/", view("TypePropertyLink", ["post"]), name=f"{tag}-type-property-links"),
        path(
            f"{t}/properties/<uuid:property_id>/",
            view("TypePropertyLink", ["delete"]),
            name=f"{tag}-type-property-link",
        ),
        path(
            f"{proj}/work-item-properties/",
            view("ProjectPropertyList", ["get", "post"]),
            name=f"{tag}-project-properties",
        ),
        path(
            f"{proj}/work-item-properties/<uuid:property_id>/",
            view("ProjectPropertyDetail", ["get", "patch", "delete"]),
            name=f"{tag}-project-property",
        ),
        path(
            f"{proj}/work-item-properties/<uuid:property_id>/options/",
            view("ProjectOptions", ["get", "post"]),
            name=f"{tag}-project-property-options",
        ),
        path(
            f"{proj}/work-item-properties/<uuid:property_id>/options/<uuid:option_id>/",
            view("ProjectOptions", ["get", "patch", "delete"]),
            name=f"{tag}-project-property-option",
        ),
        path(
            f"{proj}/work-items/<uuid:work_item_id>/work-item-properties/<uuid:property_id>/values/",
            view("Values", ALL),
            name=f"{tag}-property-values",
        ),
        path(
            f"{ws}/work-item-properties/", view("WorkspacePropertyList", ["get", "post"]), name=f"{tag}-ws-properties"
        ),
        path(
            f"{ws}/work-item-properties/<uuid:property_id>/",
            view("WorkspacePropertyDetail", ["get", "patch", "delete"]),
            name=f"{tag}-ws-property",
        ),
        path(
            f"{ws}/work-item-properties/<uuid:property_id>/options/",
            view("WorkspaceOptions", ["get", "post"]),
            name=f"{tag}-ws-property-options",
        ),
        path(
            f"{ws}/work-item-properties/<uuid:property_id>/options/<uuid:option_id>/",
            view("WorkspaceOptions", ["get", "patch", "delete"]),
            name=f"{tag}-ws-property-option",
        ),
    ]
    mview = lambda name, methods: getattr(mv, name + s).as_view(http_method_names=methods)  # noqa: E731
    mp = f"{proj}/module-properties"
    out += [
        path(f"{mp}/", mview("ModulePropertyList", ["get", "post"]), name=f"{tag}-module-properties"),
        path(
            f"{mp}/<uuid:property_id>/",
            mview("ModulePropertyDetail", ["get", "patch", "delete"]),
            name=f"{tag}-module-property",
        ),
        path(
            f"{mp}/<uuid:property_id>/options/",
            mview("ModuleOptions", ["get", "post"]),
            name=f"{tag}-module-property-options",
        ),
        path(
            f"{mp}/<uuid:property_id>/options/<uuid:option_id>/",
            mview("ModuleOptions", ["get", "patch", "delete"]),
            name=f"{tag}-module-property-option",
        ),
        path(
            f"{proj}/modules/<uuid:module_id>/module-properties/<uuid:property_id>/values/",
            mview("ModuleValues", ALL),
            name=f"{tag}-module-property-values",
        ),
        path(
            f"{proj}/modules/<uuid:module_id>/module-property-values/",
            mview("ModuleAllValues", ["get"]),
            name=f"{tag}-module-all-values",
        ),
        path(
            f"{proj}/module-property-values/",
            mview("ProjectModuleValues", ["get"]),
            name=f"{tag}-project-module-values",
        ),
    ]
    if not public:
        out.append(
            path(
                f"{proj}/work-items/<uuid:work_item_id>/property-values/",
                v.WorkItemAllValuesEndpoint.as_view(http_method_names=["get"]),
                name="oces-work-item-property-values",
            )
        )
    return out
