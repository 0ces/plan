# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item types per project (project mode).

A type is an upstream IssueType linked to one project through ProjectIssueType.
The same tables can later hold a workspace catalogue linked to many projects.
"""

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver
from rest_framework.exceptions import ValidationError

from plane.db.models import Issue, IssueType
from plane.db.models.issue_type import ProjectIssueType


def _icon(name, color):
    return {"in_use": "icon", "icon": {"name": name, "color": color}}


# Created when a project switches types on. Task is the default for new work items.
DEFAULT_TYPES = [
    {"name": "Task", "logo_props": _icon("check_circle", "#3f76ff"), "is_default": True},
    {"name": "Bug", "logo_props": _icon("bug_report", "#e5484d")},
    {"name": "Feature", "logo_props": _icon("auto_awesome", "#30a46c")},
    {"name": "Epic", "logo_props": _icon("bolt", "#8e4ec6"), "is_epic": True, "level": 1},
]


def project_types(project_id):
    """Active links first is not needed; callers filter. Ordered for stable lists."""
    return IssueType.objects.filter(project_issue_types__project_id=project_id).order_by("level", "created_at")


def default_type(project_id):
    return IssueType.objects.filter(
        project_issue_types__project_id=project_id, project_issue_types__is_default=True
    ).first()


@transaction.atomic
def enable_project_types(project):
    """Switch types on: create the defaults once and give untyped work items the default type."""
    if not ProjectIssueType.objects.filter(project=project).exists():
        for spec in DEFAULT_TYPES:
            issue_type = IssueType.objects.create(
                workspace_id=project.workspace_id,
                name=spec["name"],
                logo_props=spec["logo_props"],
                is_epic=spec.get("is_epic", False),
                is_default=spec.get("is_default", False),
                level=spec.get("level", 0),
            )
            ProjectIssueType.objects.create(
                project=project,
                issue_type=issue_type,
                level=spec.get("level", 0),
                is_default=spec.get("is_default", False),
            )
    task = default_type(project.id)
    # all_objects: archived, draft and triage items get the default too.
    Issue.all_objects.filter(project=project, type__isnull=True).update(type=task)
    project.is_issue_type_enabled = True
    project.save()


def validate_issue_type(issue_type, project_id, creating):
    """API-level check, so callers get a 400 instead of a silent fix."""
    if issue_type is None:
        return
    link = ProjectIssueType.objects.filter(project_id=project_id, issue_type=issue_type).first()
    if link is None:
        raise ValidationError({"type_id": "Work item type does not belong to this project."})
    if creating and not issue_type.is_active:
        raise ValidationError({"type_id": "Work item type is not active."})


@receiver(pre_save, sender=Issue, dispatch_uid="oces_issue_default_type")
def set_issue_type(sender, instance, raw=False, **kwargs):
    """Every work item in a project with types gets a type of that project.

    Covers all creation paths (web, API, intake, imports). A type from another
    project (e.g. after a move) is replaced by this project's default.
    """
    if raw or not instance.project_id:
        return
    if (
        instance.type_id
        and ProjectIssueType.objects.filter(project_id=instance.project_id, issue_type_id=instance.type_id).exists()
    ):
        return
    instance.type = default_type(instance.project_id)
