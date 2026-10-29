# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Epic list with child progress, for the web Epics page and the epic detail widget."""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response

from plane.app.permissions import ProjectLitePermission
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Issue, ProjectMember

GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


def visible_issues(request, slug, project_id):
    """Work items this user may see in the project (guests without full access see only their own)."""
    qs = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id)
    limited_guest = ProjectMember.objects.filter(
        project_id=project_id,
        member=request.user,
        role=5,
        is_active=True,
        project__guest_view_all_features=False,
    ).exists()
    return qs.filter(created_by=request.user) if limited_guest else qs


def progress_counts(children):
    """Counts in the TEpicAnalytics shape (packages/types/src/epics.ts) plus total."""
    today = timezone.now().date()
    agg = children.aggregate(
        **{f"{g}_issues": Count("id", filter=Q(state__group=g)) for g in GROUPS},
        overdue_issues=Count("id", filter=Q(target_date__lt=today) & ~Q(state__group__in=["completed", "cancelled"])),
        total_issues=Count("id"),
    )
    return agg


class EpicListEndpoint(AppAPIView):
    permission_classes = [ProjectLitePermission]

    def get(self, request, slug, project_id):
        issues = visible_issues(request, slug, project_id)
        epics = issues.filter(type__is_epic=True).select_related("state").order_by("-created_at")
        result = []
        for epic in epics:
            result.append(
                {
                    "id": str(epic.id),
                    "name": epic.name,
                    "sequence_id": epic.sequence_id,
                    "project_id": str(epic.project_id),
                    "type_id": str(epic.type_id),
                    "state_id": str(epic.state_id) if epic.state_id else None,
                    "priority": epic.priority,
                    "start_date": epic.start_date,
                    "target_date": epic.target_date,
                    "progress": progress_counts(issues.filter(parent=epic)),
                }
            )
        return Response(result)


class EpicProgressEndpoint(AppAPIView):
    permission_classes = [ProjectLitePermission]

    def get(self, request, slug, project_id, epic_id):
        issues = visible_issues(request, slug, project_id)
        epic = get_object_or_404(issues, pk=epic_id)
        return Response(progress_counts(issues.filter(parent=epic)))
