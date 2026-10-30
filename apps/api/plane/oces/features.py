# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Feature switches with the official Plane API key names.

plane-mcp-server reads these before it uses a paid tool, so the keys and the
flat {key: bool} shape must match the public API.
"""

# key -> attribute on our WorkspaceFeature row; None = not offered by this fork (always false).
WORKSPACE_KEYS = {
    "project_grouping": None,
    "initiatives": "initiatives",
    "teams": None,
    "customers": "customers",
    "wiki": None,
    "pi": None,
    "work_item_types": "work_item_types",
    "releases": "releases",
    "states_owned_by_workspace": None,
}

# key -> (where, attribute). "project" = upstream Project column, "oces" = our ProjectFeature row.
PROJECT_KEYS = {
    "epics": ("oces", "epics"),
    "modules": ("project", "module_view"),
    "cycles": ("project", "cycle_view"),
    "views": ("project", "issue_views_view"),
    "pages": ("project", "page_view"),
    "intakes": ("project", "intake_view"),
    "work_item_types": ("project", "is_issue_type_enabled"),
    "workflows": ("oces", "workflows"),
    "parallel_cycles": None,
    "project_updates": None,
}

# Keys that may be switched on. Each feature step adds its key when it ships.
BUILT_WORKSPACE_KEYS = frozenset({"initiatives"})
BUILT_PROJECT_KEYS = frozenset({"modules", "cycles", "views", "pages", "intakes", "work_item_types"})


def validate_changes(data, keys, built):
    """Return (changes, error). changes maps key -> bool for keys that have storage."""
    if not isinstance(data, dict) or not data:
        return None, {"error": "Send an object of feature names to true/false."}
    unknown = sorted(k for k in data if k not in keys)
    if unknown:
        return None, {"error": "Unknown features.", "features": unknown}
    not_bool = sorted(k for k, v in data.items() if not isinstance(v, bool))
    if not_bool:
        return None, {"error": "Feature values must be true or false.", "features": not_bool}
    unavailable = sorted(k for k, v in data.items() if v and k not in built)
    if unavailable:
        return None, {
            "error": "These features are not available on this edition yet.",
            "code": "feature_not_available",
            "features": unavailable,
        }
    # Turning off a feature we never offer is a no-op.
    return {k: v for k, v in data.items() if keys[k] is not None}, None
