# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Custom properties on modules: values, and progress computed from the module's work items.

Definitions are WorkItemProperty rows with entity=MODULE (see properties.py for the rules,
which are shared). Values live in ModulePropertyValue. No activity log: CE has none for modules.
"""

from django.db import transaction
from django.db.models import Exists, FloatField, OuterRef, Q, Sum
from django.db.models.functions import Cast

from plane.db.models import Issue, ModuleIssue

from . import properties as P
from .models import ModulePropertyValue


def value_out(row):
    return {
        "id": str(row.id),
        "property_id": str(row.property_id),
        "module_id": str(row.module_id),
        "value": P.raw_value(row),
        "value_type": row.property.property_type,
        "external_id": row.external_id,
        "external_source": row.external_source,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def values_response(prop, rows):
    out = [value_out(r) for r in rows]
    return out if prop.is_multi else (out[0] if out else None)


def rows_for(prop, module):
    rows = list(prop.module_values.filter(module=module).select_related("value_option"))
    for r in rows:
        r.property = prop
    return rows


@transaction.atomic
def set_values(prop, module, raw, external=None):
    """Replace the module's values for this property. Returns the new rows."""
    columns = P.parse_values(prop, raw, module)
    prop.module_values.filter(module=module).delete(soft=False)
    rows = [
        ModulePropertyValue.objects.create(
            workspace_id=module.workspace_id,
            project_id=module.project_id,
            module=module,
            property=prop,
            **cols,
            **(external or {}),
        )
        for cols in columns
    ]
    for r in rows:
        r.property = prop
    return rows


def clear_values(prop, module):
    prop.module_values.filter(module=module).delete(soft=False)


def all_values(module_ids):
    """{module_id: {property_id: value | [values]}} for the given modules."""
    out = {str(m): {} for m in module_ids}
    rows = ModulePropertyValue.objects.filter(
        module_id__in=module_ids, property__deleted_at__isnull=True, property__is_active=True
    ).select_related("property")
    for r in rows:
        values = out[str(r.module_id)]
        key = str(r.property_id)
        if r.property.is_multi:
            values.setdefault(key, []).append(P.raw_value(r))
        else:
            values[key] = P.raw_value(r)
    return out


def computed(module):
    """Counts and points of the module's top-level work items.

    A sub-item whose parent is in the same module is left out, so a story and its tasks
    count once (module = epic, work items = stories, sub-items = tasks). Points use the
    project's estimate only when it is a points estimate, as Plane's own sidebar does.
    """
    in_module = ModuleIssue.objects.filter(module=module, deleted_at__isnull=True)
    parent_in_module = in_module.filter(issue_id=OuterRef("parent_id"))
    items = Issue.issue_objects.filter(issue_module__module=module, issue_module__deleted_at__isnull=True).exclude(
        Exists(parent_in_module)
    )
    done = Q(state__group="completed")
    total = items.count()
    completed = items.filter(done).count()
    pointed = items.filter(estimate_point__estimate__type="points")
    points = lambda qs: qs.aggregate(n=Sum(Cast("estimate_point__value", FloatField())))["n"] or 0  # noqa: E731
    return {
        "work_items": total,
        "work_items_done": completed,
        "work_items_cancelled": items.filter(state__group="cancelled").count(),
        "points_total": points(pointed),
        "points_done": points(pointed.filter(done)),
        "progress": round(100 * completed / total) if total else 0,
    }
