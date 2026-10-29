# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item list endpoints with PQL (official /api/v1 paths).

- projects/{p}/work-items/          overrides upstream's GET, which rejects ?pql=
- work-items/                       workspace-wide list (not in CE)
- projects/{p}/archived-work-items/ archived list (not in CE)
- work-items/count/                 grouped counts (not in CE)
"""

from collections import defaultdict

from django.db.models import Count, F, Func, OuterRef, Q
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import IssueSerializer
from plane.api.views.base import BaseAPIView
from plane.api.views.issue import IssueListCreateAPIEndpoint
from plane.app.permissions import ProjectEntityPermission, WorkspaceUserPermission
from plane.db.models import Issue, ProjectMember
from plane.utils.order_queryset import ISSUE_ORDER_BY_ALLOWLIST, sanitize_order_by

from .pql import PQLError, parse_pql

# Count group_by values from the official API -> ORM path. Others are rejected.
COUNT_GROUPS = {
    "state_id": "state_id",
    "state__group": "state__group",
    "priority": "priority",
    "project_id": "project_id",
    "type_id": "type_id",
    "labels__id": "label_issue__label_id",
    "assignees__id": "issue_assignee__assignee_id",
    "issue_module__module_id": "issue_module__module_id",
    "cycle_id": "issue_cycle__cycle_id",
    "created_by": "created_by_id",
    "target_date": "target_date",
    "start_date": "start_date",
}
# Through-table paths whose soft-deleted rows must not be counted.
LIVE_LINK = {
    "label_issue__label_id": "label_issue__deleted_at__isnull",
    "issue_assignee__assignee_id": "issue_assignee__deleted_at__isnull",
    "issue_module__module_id": "issue_module__deleted_at__isnull",
    "issue_cycle__cycle_id": "issue_cycle__deleted_at__isnull",
}


def visible_work_items(queryset, user, slug, project_id=None):
    """Limit to projects the user belongs to; guests without full access see only what they created."""
    members = ProjectMember.objects.filter(member=user, workspace__slug=slug, is_active=True)
    if project_id:
        members = members.filter(project_id=project_id)
    full = members.filter(Q(role__gte=15) | Q(project__guest_view_all_features=True)).values("project_id")
    limited = members.filter(role=5, project__guest_view_all_features=False).values("project_id")
    return queryset.filter(workspace__slug=slug).filter(
        Q(project_id__in=full) | Q(project_id__in=limited, created_by=user)
    )


def pql_error(exc):
    return Response({"pql": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PQLListMixin:
    def apply_pql(self, queryset, project_id=None):
        """Returns the filtered queryset; raises PQLError on bad PQL."""
        pql = self.request.GET.get("pql")
        if self.request.GET.get("filters"):
            raise PQLError("Structured filters are not supported on this edition; use pql.")
        if not pql:
            return queryset
        return queryset.filter(parse_pql(pql, self.request.user, self.kwargs["slug"], project_id)).distinct()

    def list_response(self, request, queryset):
        # shortcut: priority/state/label/assignee custom orderings fall back to -created_at here.
        requested = request.GET.get("order_by", "-created_at")
        order_by = sanitize_order_by(requested, ISSUE_ORDER_BY_ALLOWLIST, "-created_at")
        if "__" in order_by or order_by.lstrip("-") == "priority":
            order_by = "-created_at"
        queryset = queryset.annotate(
            sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
            .order_by()
            .annotate(count=Func(F("id"), function="Count"))
            .values("count")
        ).select_related("project", "workspace", "state", "parent")
        return self.paginate(
            request=request,
            queryset=queryset.order_by(order_by),
            total_count_queryset=queryset,
            on_results=lambda issues: IssueSerializer(issues, many=True, fields=self.fields, expand=self.expand).data,
        )


class ProjectWorkItemListAPIEndpoint(PQLListMixin, IssueListCreateAPIEndpoint):
    """Upstream list + create; GET with ?pql= is handled here, everything else by upstream."""

    def get(self, request, slug, project_id):
        if not request.GET.get("pql"):
            return super().get(request, slug, project_id)
        try:
            queryset = self.apply_pql(
                visible_work_items(Issue.issue_objects.filter(project_id=project_id), request.user, slug, project_id),
                project_id,
            )
        except PQLError as exc:
            return pql_error(exc)
        return self.list_response(request, queryset)


class WorkspaceWorkItemListAPIEndpoint(PQLListMixin, BaseAPIView):
    permission_classes = [WorkspaceUserPermission]

    def get(self, request, slug):
        try:
            queryset = self.apply_pql(visible_work_items(Issue.issue_objects.all(), request.user, slug))
        except PQLError as exc:
            return pql_error(exc)
        return self.list_response(request, queryset)


class ArchivedWorkItemListAPIEndpoint(PQLListMixin, BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        base = Issue.objects.filter(project_id=project_id, archived_at__isnull=False, is_draft=False)
        try:
            queryset = self.apply_pql(visible_work_items(base, request.user, slug, project_id), project_id)
        except PQLError as exc:
            return pql_error(exc)
        return self.list_response(request, queryset)


class WorkItemCountAPIEndpoint(PQLListMixin, BaseAPIView):
    permission_classes = [WorkspaceUserPermission]

    def get(self, request, slug):
        group_by, sub_group_by = request.GET.get("group_by"), request.GET.get("sub_group_by")
        for value in (group_by, sub_group_by):
            if value and value not in COUNT_GROUPS:
                return Response(
                    {"error": f"group_by must be one of {sorted(COUNT_GROUPS)}."}, status=status.HTTP_400_BAD_REQUEST
                )
        if sub_group_by and not group_by:
            return Response({"error": "sub_group_by needs group_by."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            queryset = self.apply_pql(visible_work_items(Issue.issue_objects.all(), request.user, slug))
        except PQLError as exc:
            return pql_error(exc)

        body = {
            "grouped_by": group_by,
            "sub_grouped_by": sub_group_by,
            "total_count": queryset.values("id").distinct().count(),
            "grouped_counts": {},
        }
        if not group_by:
            return Response(body)

        columns = [COUNT_GROUPS[g] for g in (group_by, sub_group_by) if g]
        rows = Issue.issue_objects.filter(id__in=queryset.values("id"))
        for column in columns:
            # shortcut: an item whose only links are soft-deleted drops out instead of counting under "None".
            if column in LIVE_LINK:
                rows = rows.filter(Q(**{LIVE_LINK[column]: True}) | Q(**{f"{column}__isnull": True}))
        rows = rows.values(*columns).annotate(count=Count("id", distinct=True)).order_by()

        grouped = defaultdict(lambda: {"count": 0})
        for row in rows:
            key = str(row[columns[0]])
            if sub_group_by:
                sub = grouped[key].setdefault("sub_grouped_counts", {})
                sub[str(row[columns[1]])] = {"count": row["count"]}
            else:
                grouped[key]["count"] = row["count"]
        if sub_group_by:
            # A work item counts once per group even when it falls in several sub-groups.
            for row in (
                Issue.issue_objects.filter(id__in=queryset.values("id"))
                .values(columns[0])
                .annotate(count=Count("id", distinct=True))
                .order_by()
            ):
                grouped[str(row[columns[0]])]["count"] = row["count"]
        body["grouped_counts"] = dict(grouped)
        return Response(body)
