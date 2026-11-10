# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Time logs on work items. Paths and fields follow Plane's public API so plane-mcp-server's work_log tool works.

projects/{p}/work-items/{w}/worklogs/[{id}/]   one work item's entries (members write, own or admin edits)
projects/{p}/worklogs/summary/                 total minutes per work item
projects/{p}/worklogs/?from=&to=&logged_by=    entries in a date range, for the timesheet
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from plane.db.models import Issue, Project, ProjectMember

from .models import WorkLog
from .property_views import _pair

ADMIN, MEMBER = 20, 15
MAX_MINUTES = 24 * 60
MAX_RANGE_DAYS = 366


class ProjectMemberOnly(BasePermission):
    """Members and admins of the project. Guests do not see or log time."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        kw = view.kwargs
        return ProjectMember.objects.filter(
            workspace__slug=kw["slug"],
            project_id=kw["project_id"],
            member=request.user,
            role__in=[ADMIN, MEMBER],
            is_active=True,
        ).exists()


def work_log_out(log):
    return {
        "id": str(log.id),
        "work_item_id": str(log.issue_id),
        "project_id": str(log.project_id),
        "workspace_id": str(log.workspace_id),
        "duration": log.duration,
        "description": log.description,
        "logged_at": log.logged_at.isoformat(),
        "logged_by": str(log.logged_by_id),
        "created_by": str(log.created_by_id) if log.created_by_id else None,
        "updated_by": str(log.updated_by_id) if log.updated_by_id else None,
        "created_at": log.created_at.isoformat(),
        "updated_at": log.updated_at.isoformat(),
    }


def _date(value, field):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError({field: "Use a date like 2026-11-10."})


def clean(data, partial):
    """Validate a create/update body. Returns the fields to set."""
    if not isinstance(data, dict):
        raise ValidationError({"error": "Send a JSON object."})
    out = {}
    if "duration" in data or not partial:
        d = data.get("duration")
        if isinstance(d, bool) or not isinstance(d, int) or not 0 < d <= MAX_MINUTES:
            raise ValidationError({"duration": f"Minutes, a whole number from 1 to {MAX_MINUTES}."})
        out["duration"] = d
    if "description" in data:
        text = data["description"] or ""
        if not isinstance(text, str) or len(text) > 2000:
            raise ValidationError({"description": "Text up to 2000 characters."})
        out["description"] = text.strip()
    if data.get("logged_at"):
        out["logged_at"] = _date(data["logged_at"], "logged_at")
    return out


def today_for(user):
    try:
        return datetime.now(ZoneInfo(user.user_timezone or "UTC")).date()
    except (KeyError, ValueError):
        return date.today()


class WorkLogScope:
    def get_permissions(self):
        return [ProjectMemberOnly()]

    def project(self, slug, project_id):
        return get_object_or_404(Project, pk=project_id, workspace__slug=slug)

    def work_item(self, slug, project_id, work_item_id):
        return get_object_or_404(Issue.objects, pk=work_item_id, project_id=project_id, workspace__slug=slug)

    def require_enabled(self, project):
        if not project.is_time_tracking_enabled:
            raise ValidationError({"error": "Time tracking is off for this project.", "code": "time_tracking_disabled"})


class WorkLogListMixin(WorkLogScope):
    def get(self, request, slug, project_id, work_item_id):
        item = self.work_item(slug, project_id, work_item_id)
        return Response([work_log_out(x) for x in WorkLog.objects.filter(issue=item)])

    def post(self, request, slug, project_id, work_item_id):
        item = self.work_item(slug, project_id, work_item_id)
        self.require_enabled(item.project)
        fields = clean(request.data, partial=False)
        fields.setdefault("logged_at", today_for(request.user))
        log = WorkLog.objects.create(
            workspace_id=item.workspace_id, project_id=item.project_id, issue=item, logged_by=request.user, **fields
        )
        return Response(work_log_out(log), status=status.HTTP_201_CREATED)


class WorkLogDetailMixin(WorkLogScope):
    def _get(self, request, slug, project_id, work_item_id, work_log_id, write):
        item = self.work_item(slug, project_id, work_item_id)
        log = get_object_or_404(WorkLog.objects, pk=work_log_id, issue=item)
        if write and log.logged_by_id != request.user.id:
            is_admin = ProjectMember.objects.filter(
                project_id=project_id, member=request.user, role=ADMIN, is_active=True
            ).exists()
            if not is_admin:
                raise PermissionDenied("Only the person who logged this time or a project admin can change it.")
        return item, log

    def get(self, request, slug, project_id, work_item_id, work_log_id):
        return Response(work_log_out(self._get(request, slug, project_id, work_item_id, work_log_id, False)[1]))

    def patch(self, request, slug, project_id, work_item_id, work_log_id):
        item, log = self._get(request, slug, project_id, work_item_id, work_log_id, True)
        self.require_enabled(item.project)
        for k, v in clean(request.data, partial=True).items():
            setattr(log, k, v)
        log.save()
        return Response(work_log_out(log))

    def delete(self, request, slug, project_id, work_item_id, work_log_id):
        self._get(request, slug, project_id, work_item_id, work_log_id, True)[1].delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _live(project):
    """Entries whose work item still exists."""
    return WorkLog.objects.filter(project=project, issue__deleted_at__isnull=True)


class WorkLogSummaryMixin(WorkLogScope):
    def get(self, request, slug, project_id):
        rows = (
            _live(self.project(slug, project_id))
            .values("issue_id")
            .annotate(total=Sum("duration"))
            .order_by("issue_id")
        )
        return Response([{"work_item_id": str(r["issue_id"]), "duration": r["total"]} for r in rows])


class ProjectWorkLogsMixin(WorkLogScope):
    def get(self, request, slug, project_id):
        project = self.project(slug, project_id)
        today = today_for(request.user)
        start = (
            _date(request.query_params["from"], "from") if request.query_params.get("from") else today - timedelta(6)
        )
        end = _date(request.query_params["to"], "to") if request.query_params.get("to") else today
        if end < start or (end - start).days >= MAX_RANGE_DAYS:
            raise ValidationError({"error": f"'to' must be on or after 'from', at most {MAX_RANGE_DAYS} days apart."})
        qs = _live(project).filter(logged_at__range=(start, end)).select_related("issue")
        if request.query_params.get("logged_by"):
            try:
                qs = qs.filter(logged_by_id=uuid.UUID(request.query_params["logged_by"]))
            except ValueError:
                raise ValidationError({"logged_by": "Must be a user id."})
        out = []
        for log in qs:
            row = work_log_out(log)
            row["work_item"] = {"id": str(log.issue_id), "sequence_id": log.issue.sequence_id, "name": log.issue.name}
            out.append(row)
        return Response({"from": start.isoformat(), "to": end.isoformat(), "results": out})


WorkLogListAPIEndpoint, WorkLogListEndpoint = _pair(WorkLogListMixin)
WorkLogDetailAPIEndpoint, WorkLogDetailEndpoint = _pair(WorkLogDetailMixin)
WorkLogSummaryAPIEndpoint, WorkLogSummaryEndpoint = _pair(WorkLogSummaryMixin)
ProjectWorkLogsAPIEndpoint, ProjectWorkLogsEndpoint = _pair(ProjectWorkLogsMixin)
