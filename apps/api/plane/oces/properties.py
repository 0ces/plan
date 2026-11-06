# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Custom work item properties: definition rules, value parsing and output.

Shapes follow the official public API (see docs/fork/api-contract.md, section b),
so plane-mcp-server works unchanged.
"""

import uuid
from datetime import datetime, time
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from plane.db.models import Issue, IssueActivity, Module, ProjectMember, User, WorkspaceMember
from plane.utils.content_validator import validate_html_content

from .models import WorkItemProperty, WorkItemPropertyOption, WorkItemPropertyValue, WorkItemTypeProperty

PROPERTY_TYPES = {
    "TEXT",
    "DATETIME",
    "DECIMAL",
    "BOOLEAN",
    "OPTION",
    "RELATION",
    "URL",
    "EMAIL",
    "FILE",
    "FORMULA",
    "CASCADING",
}
NOT_YET = {"FILE", "FORMULA", "CASCADING"}
RELATION_TYPES = {"ISSUE", "USER", "RELEASE", "RICH_TEXT", "MODULE"}
RELATION_NOT_YET = {"RELEASE"}
TEXT_FORMATS = {"single-line", "multi-line", "readonly"}
DATE_FORMATS = {"MMM dd, yyyy", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy/MM/dd"}
RICH_TEXT_ERROR = "Rich text value must be an object with description_html."
ACTIVITY_FIELD = "oces_property"
MAX_TEXT = 10_000

DEFINITION_FIELDS = {
    "display_name",
    "description",
    "logo_props",
    "sort_order",
    "property_type",
    "relation_type",
    "settings",
    "is_required",
    "is_multi",
    "is_active",
    "default_value",
    "validation_rules",
    "external_source",
    "external_id",
}
OPTION_FIELDS = {
    "name",
    "description",
    "logo_props",
    "sort_order",
    "is_active",
    "is_default",
    "external_source",
    "external_id",
}


def stored_values(prop):
    """The value rows of a definition, whichever entity it is for."""
    return prop.module_values if prop.entity == "MODULE" else prop.values


def is_rich_text(prop):
    return prop.property_type == "RELATION" and prop.relation_type == "RICH_TEXT"


# ---------------------------------------------------------------- definitions


def clean_definition(data, instance=None, entity="ISSUE"):
    """Validate a create/update body. Returns the fields to save; raises ValidationError (400)."""
    if not isinstance(data, dict):
        raise ValidationError({"error": "Send a JSON object."})
    out = {k: v for k, v in data.items() if k in DEFINITION_FIELDS}
    merged = {
        "property_type": instance.property_type if instance else None,
        "relation_type": instance.relation_type if instance else None,
        "settings": instance.settings if instance else None,
        "is_multi": instance.is_multi if instance else False,
    }
    merged.update({k: out[k] for k in merged if k in out})

    if instance is None or "display_name" in out:
        name = str(out.get("display_name") or "").strip()
        if not name:
            raise ValidationError({"display_name": "display_name is required."})
        if len(name) > 255:
            raise ValidationError({"display_name": "display_name is too long (255 characters max)."})
        out["display_name"] = name
        out["name"] = slugify(name)[:255] or name.lower()

    ptype = merged["property_type"]
    if ptype not in PROPERTY_TYPES:
        raise ValidationError({"property_type": f"property_type must be one of {sorted(PROPERTY_TYPES)}."})
    if ptype in NOT_YET:
        raise ValidationError({"property_type": f"{ptype} properties are not supported on this edition yet."})
    if instance:
        entity = instance.entity
    if instance and "property_type" in out and ptype != instance.property_type and stored_values(instance).exists():
        raise ValidationError({"property_type": "property_type cannot change while values are set."})

    if ptype == "RELATION":
        rtype = merged["relation_type"]
        if rtype not in RELATION_TYPES:
            raise ValidationError({"relation_type": "relation_type is required for RELATION properties."})
        if rtype in RELATION_NOT_YET:
            raise ValidationError({"relation_type": f"{rtype} relations are not supported on this edition yet."})
        if (rtype == "MODULE" and entity != "MODULE") or (rtype == "RICH_TEXT" and entity == "MODULE"):
            raise ValidationError({"relation_type": f"{rtype} relations are not available here."})
    else:
        out["relation_type"] = None

    settings = merged["settings"]
    fmt = settings.get("display_format") if isinstance(settings, dict) else None
    if ptype == "TEXT":
        if fmt not in TEXT_FORMATS:
            raise ValidationError({"settings": f"TEXT needs settings.display_format, one of {sorted(TEXT_FORMATS)}."})
        out["settings"] = {"display_format": fmt}
    elif ptype == "DATETIME":
        if fmt not in DATE_FORMATS:
            raise ValidationError(
                {"settings": f"DATETIME needs settings.display_format, one of {sorted(DATE_FORMATS)}."}
            )
        out["settings"] = {"display_format": fmt}
    else:
        out["settings"] = None

    multi_ok = ptype == "OPTION" or (ptype == "RELATION" and merged["relation_type"] in ("USER", "ISSUE", "MODULE"))
    if merged["is_multi"] and not multi_ok:
        raise ValidationError({"is_multi": "Only OPTION and USER/ISSUE/MODULE relation properties can be multi-value."})
    if instance and "is_multi" in out and not out["is_multi"] and instance.is_multi:
        owner = "module_id" if entity == "MODULE" else "issue_id"
        many = stored_values(instance).values(owner).annotate(n=Count("id"))
        if many.filter(n__gt=1).exists():
            raise ValidationError(
                {"is_multi": "Some items have several values. Remove them before turning is_multi off."}
            )

    if "default_value" in out:
        dv = out["default_value"]
        if dv in (None, ""):
            dv = []
        if not isinstance(dv, list):
            dv = [dv]
        out["default_value"] = [str(v) for v in dv]
    for flag in ("is_required", "is_multi", "is_active"):
        if flag in out and not isinstance(out[flag], bool):
            raise ValidationError({flag: f"{flag} must be true or false."})
    if "logo_props" in out and not isinstance(out["logo_props"], dict):
        raise ValidationError({"logo_props": "logo_props must be an object."})
    return out


def check_unique_name(prop_qs, display_name, exclude_id=None):
    qs = prop_qs.filter(display_name__iexact=display_name)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    if qs.exists():
        raise ValidationError({"display_name": "A property with this name already exists here."})


def clean_option(data, prop, instance=None):
    if not isinstance(data, dict):
        raise ValidationError({"error": "Send a JSON object."})
    out = {k: v for k, v in data.items() if k in OPTION_FIELDS}
    if data.get("color"):  # the MCP sends a colour; we keep it in logo_props like labels do
        out["logo_props"] = {**(out.get("logo_props") or {}), "in_use": "color", "color": str(data["color"])}
    if instance is None or "name" in out:
        name = str(out.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Option name is required."})
        out["name"] = name[:255]
        clash = prop.options.filter(name__iexact=name)
        if instance:
            clash = clash.exclude(pk=instance.pk)
        if clash.exists():
            raise ValidationError({"name": "An option with this name already exists."})
    return out


@transaction.atomic
def save_option(prop, data, instance=None):
    fields = clean_option(data, prop, instance)
    if instance is None:
        last = prop.options.order_by("-sort_order").values_list("sort_order", flat=True).first()
        fields.setdefault("sort_order", (last or 0) + 10_000)
        instance = WorkItemPropertyOption(property=prop, workspace_id=prop.workspace_id, project_id=prop.project_id)
    for k, v in fields.items():
        setattr(instance, k, v)
    instance.save()
    if instance.is_default and not prop.is_multi:
        prop.options.exclude(pk=instance.pk).update(is_default=False)
    return instance


@transaction.atomic
def replace_options(prop, items):
    """Make the option list match `items` ({id?, name, color?, is_default?}): matched by id, then by name;
    new names are added, options left out are deleted (with the values that use them)."""
    if prop.property_type != "OPTION":
        raise ValidationError({"options": "Only OPTION properties have options."})
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValidationError({"options": "options must be a list of objects."})
    current = list(prop.options.all())
    by_id = {str(o.id): o for o in current}
    by_name = {o.name.lower(): o for o in current}
    keep = []
    for index, item in enumerate(items):
        option = by_id.get(str(item.get("id"))) or by_name.get(str(item.get("name") or "").strip().lower())
        data = {**item, "sort_order": (index + 1) * 10_000}
        data.pop("id", None)
        if option and str(data.get("name") or "").strip().lower() == option.name.lower():
            data.pop("name")  # unchanged name: skip the duplicate-name check
        saved = save_option(prop, data, option)
        keep.append(saved.id)
    prop.options.exclude(pk__in=keep).delete(soft=False)


@transaction.atomic
def create_property(*, workspace_id, project_id, issue_type, data, scope_qs, entity="ISSUE"):
    fields = clean_definition(data, entity=entity)
    check_unique_name(scope_qs, fields["display_name"])
    if (
        fields["property_type"] == "OPTION"
        and data.get("options") is not None
        and not isinstance(data["options"], list)
    ):
        raise ValidationError({"options": "options must be a list."})
    last = scope_qs.order_by("-sort_order").values_list("sort_order", flat=True).first()
    fields.setdefault("sort_order", (last or 0) + 10_000)
    prop = WorkItemProperty.all_objects.create(
        workspace_id=workspace_id, project_id=project_id, issue_type=issue_type, entity=entity, **fields
    )
    if issue_type is not None:
        WorkItemTypeProperty.objects.create(issue_type=issue_type, property=prop)
    if prop.property_type == "OPTION":
        for item in data.get("options") or []:
            save_option(prop, item)
    return prop


def update_property(prop, data, scope_qs):
    fields = clean_definition(data, instance=prop)
    if "display_name" in fields:
        check_unique_name(scope_qs, fields["display_name"], exclude_id=prop.id)
    for k, v in fields.items():
        setattr(prop, k, v)
    prop.save()
    return prop


@transaction.atomic
def delete_property(prop):
    stored_values(prop).all().delete(soft=False)
    WorkItemTypeProperty.objects.filter(property=prop).delete(soft=False)
    prop.options.all().delete(soft=False)
    prop.delete(soft=False)


# ---------------------------------------------------------------- values


def _parse_datetime(raw):
    if not isinstance(raw, str):
        raise ValidationError({"value": "DATETIME needs a string like 2026-10-30 or 2026-10-30 14:00:00."})
    text = raw.strip().replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            value = datetime.strptime(text[:19], fmt)
            return timezone.make_aware(value, dt_timezone.utc)
        except ValueError:
            continue
    raise ValidationError({"value": "DATETIME needs a string like 2026-10-30 or 2026-10-30 14:00:00."})


def _as_uuid(raw):
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        raise ValidationError({"value": f"{raw!r} is not a valid id."})


def parse_values(prop, raw, issue):
    """Turn a request value into a list of column dicts, one per stored row.

    `issue` is the owner of the value: a work item, or a module for module properties."""
    ptype = prop.property_type
    if is_rich_text(prop):
        if not isinstance(raw, dict) or not isinstance(raw.get("description_html"), str):
            raise ValidationError({"value": RICH_TEXT_ERROR})
        ok, error, clean = validate_html_content(raw["description_html"])
        if not ok:
            raise ValidationError({"value": error})
        return [{"value_text": clean or ""}]

    many = ptype in ("OPTION", "RELATION") and prop.is_multi
    if isinstance(raw, list):
        if not many:
            raise ValidationError({"value": "This property takes one value, not a list."})
        items = raw
    else:
        items = [raw]
    if many and len(items) != len({str(i) for i in items}):
        raise ValidationError({"value": "The list has duplicates."})

    rows = []
    for item in items:
        if ptype in ("TEXT", "URL", "EMAIL"):
            if not isinstance(item, str):
                raise ValidationError({"value": f"{ptype} needs a string."})
            text = item.strip() if ptype != "TEXT" else item
            if len(text) > MAX_TEXT:
                raise ValidationError({"value": f"Text is too long ({MAX_TEXT} characters max)."})
            try:
                if ptype == "URL":
                    URLValidator()(text)
                if ptype == "EMAIL":
                    EmailValidator()(text)
            except DjangoValidationError:
                raise ValidationError({"value": f"{text!r} is not a valid {ptype.lower()}."})
            if (
                ptype == "TEXT"
                and prop.settings
                and prop.settings.get("display_format") == "single-line"
                and "\n" in text
            ):
                raise ValidationError({"value": "This is a single-line text property."})
            rows.append({"value_text": text})
        elif ptype == "DECIMAL":
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValidationError({"value": "DECIMAL needs a number, not a string."})
            try:
                rows.append({"value_decimal": Decimal(str(item))})
            except InvalidOperation:
                raise ValidationError({"value": "DECIMAL needs a number."})
        elif ptype == "BOOLEAN":
            if not isinstance(item, bool):
                raise ValidationError({"value": "BOOLEAN needs true or false."})
            rows.append({"value_boolean": item})
        elif ptype == "DATETIME":
            rows.append({"value_datetime": _parse_datetime(item)})
        elif ptype == "OPTION":
            option = prop.options.filter(pk=_as_uuid(item)).first()
            if option is None:
                raise ValidationError({"value": f"Option {item} does not belong to this property."})
            if not option.is_active:
                raise ValidationError({"value": f"Option {option.name!r} is not active."})
            rows.append({"value_option": option})
        elif ptype == "RELATION":
            target = _as_uuid(item)
            if prop.relation_type == "USER":
                if not WorkspaceMember.objects.filter(
                    workspace_id=issue.workspace_id, member_id=target, is_active=True
                ).exists():
                    raise ValidationError({"value": f"User {item} is not a member of this workspace."})
            elif prop.relation_type == "ISSUE":
                if not Issue.issue_objects.filter(workspace_id=issue.workspace_id, pk=target).exists():
                    raise ValidationError({"value": f"Work item {item} not found in this workspace."})
            elif prop.relation_type == "MODULE":
                if target == issue.pk:
                    raise ValidationError({"value": "A module cannot link to itself."})
                if not Module.objects.filter(project_id=issue.project_id, pk=target).exists():
                    raise ValidationError({"value": f"Module {item} not found in this project."})
            rows.append({"value_uuid": target})
    return rows


def raw_value(row):
    """The stored value as the API shows it."""
    prop = row.property
    ptype = prop.property_type
    if is_rich_text(prop):
        return str(row.id)
    if ptype in ("TEXT", "URL", "EMAIL"):
        return row.value_text
    if ptype == "DECIMAL":
        return float(row.value_decimal) if row.value_decimal is not None else None
    if ptype == "BOOLEAN":
        return row.value_boolean
    if ptype == "DATETIME":
        if row.value_datetime is None:
            return None
        d = row.value_datetime.astimezone(dt_timezone.utc)
        return d.strftime("%Y-%m-%d") if d.time() == time(0) else d.strftime("%Y-%m-%d %H:%M:%S")
    if ptype == "OPTION":
        return str(row.value_option_id) if row.value_option_id else None
    return str(row.value_uuid) if row.value_uuid else None


def value_out(row):
    detail = None
    if is_rich_text(row.property):
        html = row.value_text or ""
        detail = {"id": str(row.id), "description_html": html, "description_stripped": strip_tags(html)}
    return {
        "id": str(row.id),
        "property_id": str(row.property_id),
        "issue_id": str(row.issue_id),
        "value": raw_value(row),
        "value_type": row.property.property_type,
        "value_detail": detail,
        "external_id": row.external_id,
        "external_source": row.external_source,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def values_response(prop, rows):
    """Multi-value properties answer with a list, others with one object."""
    out = [value_out(r) for r in rows]
    return out if prop.is_multi else (out[0] if out else None)


def display(prop, rows):
    """Human text for activity: option names, numbers, dates."""
    parts = []
    for r in rows:
        if prop.property_type == "OPTION" and r.value_option_id:
            parts.append(r.value_option.name)
        elif is_rich_text(prop):
            parts.append(strip_tags(r.value_text or "")[:200])
        elif prop.relation_type == "USER" and r.value_uuid:
            user = User.objects.filter(pk=r.value_uuid).only("display_name").first()
            parts.append(user.display_name if user else str(r.value_uuid))
        elif prop.relation_type == "MODULE" and r.value_uuid:
            module = Module.all_objects.filter(pk=r.value_uuid).only("name").first()
            parts.append(module.name if module else str(r.value_uuid))
        elif prop.relation_type == "ISSUE" and r.value_uuid:
            item = Issue.all_objects.filter(pk=r.value_uuid).select_related("project").first()
            parts.append(f"{item.project.identifier}-{item.sequence_id}" if item else str(r.value_uuid))
        else:
            parts.append(str(raw_value(r)))
    return ", ".join(p for p in parts if p) or None


@transaction.atomic
def set_values(prop, issue, raw, actor, external=None):
    """Replace the work item's values for this property. Returns the new rows."""
    columns = parse_values(prop, raw, issue)
    old = list(prop.values.filter(issue=issue).select_related("value_option"))
    before = display(prop, old)
    WorkItemPropertyValue.objects.filter(pk__in=[r.pk for r in old]).delete(soft=False)
    rows = [
        WorkItemPropertyValue.objects.create(
            workspace_id=issue.workspace_id,
            project_id=issue.project_id,
            issue=issue,
            property=prop,
            **cols,
            **(external or {}),
        )
        for cols in columns
    ]
    for r in rows:
        r.property = prop
    record_activity(prop, issue, actor, before, display(prop, rows))
    return rows


@transaction.atomic
def clear_values(prop, issue, actor):
    old = list(prop.values.filter(issue=issue).select_related("value_option"))
    if not old:
        return
    before = display(prop, old)
    WorkItemPropertyValue.objects.filter(pk__in=[r.pk for r in old]).delete(soft=False)
    record_activity(prop, issue, actor, before, None)


def record_activity(prop, issue, actor, old, new):
    if old == new:
        return
    IssueActivity.objects.create(
        issue=issue,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        actor=actor if actor and actor.is_authenticated else None,
        verb="updated",
        field=ACTIVITY_FIELD,
        old_value=old,
        new_value=new,
        comment=prop.display_name,
        new_identifier=prop.id,
        epoch=int(timezone.now().timestamp()),
    )


# ---------------------------------------------------------------- scope helpers


def type_properties(issue_type_id):
    return WorkItemProperty.objects.filter(type_links__issue_type_id=issue_type_id).distinct()


def visible_properties(workspace_slug, user):
    """Workspace-level properties plus those of projects the user belongs to."""
    projects = ProjectMember.objects.filter(workspace__slug=workspace_slug, member=user, is_active=True).values(
        "project_id"
    )
    return WorkItemProperty.objects.filter(workspace__slug=workspace_slug).filter(
        Q(project__isnull=True) | Q(project_id__in=projects)
    )


def can_see_issue(user, issue):
    """Guests without guest_view_all_features only see work items they created."""
    member = ProjectMember.objects.filter(project_id=issue.project_id, member=user, is_active=True).first()
    if member is None:
        return False
    if member.role == 5 and not issue.project.guest_view_all_features:
        return issue.created_by_id == user.id
    return True


@transaction.atomic
def apply_defaults(issue):
    """Give a new work item its type's default values (default_value, or default options)."""
    if not issue.type_id:
        return
    for prop in type_properties(issue.type_id).filter(is_active=True):
        if prop.values.filter(issue=issue).exists():
            continue
        raw = None
        if prop.property_type == "OPTION":
            ids = [str(o) for o in prop.options.filter(is_default=True, is_active=True).values_list("id", flat=True)]
            raw = (ids if prop.is_multi else ids[:1]) or None
            if raw and not prop.is_multi:
                raw = raw[0]
        elif prop.default_value and not is_rich_text(prop):
            first = prop.default_value[0]
            raw = _default_from_text(prop, first)
        if raw is None:
            continue
        try:
            rows = parse_values(prop, raw, issue)
        except ValidationError:
            continue  # a stale default never blocks creating the work item
        for cols in rows:
            WorkItemPropertyValue.objects.create(
                workspace_id=issue.workspace_id, project_id=issue.project_id, issue=issue, property=prop, **cols
            )


def _default_from_text(prop, text):
    """default_value is a list of strings in the API; turn it into the property's own type."""
    if prop.property_type == "DECIMAL":
        try:
            return float(text)
        except ValueError:
            return None
    if prop.property_type == "BOOLEAN":
        return str(text).lower() == "true"
    if prop.property_type == "RELATION" and prop.is_multi:
        return [text]
    return text


@receiver(post_save, sender=Issue, dispatch_uid="oces_issue_property_defaults")
def issue_created(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.type_id:
        transaction.on_commit(lambda: apply_defaults(instance))
