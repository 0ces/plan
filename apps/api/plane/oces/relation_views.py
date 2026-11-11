# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item relations on the public API, in the shapes plane-sdk 0.3.1 (Plane MCP 0.3.x) calls.

Upstream CE only serves GET/POST .../work-items/{id}/relations/. The MCP's workitem_relation tool calls:

GET|POST  .../work-items/{id}/dependencies/                    list / create (the six directional types)
DELETE    .../work-items/{id}/dependencies/{related_id}/       delete, is_dependency=true
GET       .../work-items/{id}/work-item-relations/             list (relates_to, duplicate)
DELETE    .../work-items/{id}/work-item-relations/{related_id}/ delete, is_dependency=false (the default)
POST      .../work-items/{id}/relations/remove/                 SDK relations.delete, body {"related_issue"}
GET       workspaces/{slug}/work-item-relation-definitions/     list_definitions (CE has none: empty page)

CE stores every relation in one table, so the MCP's "custom relations" map onto the built-in
relates_to / duplicate types. Deletes remove the row in either direction and write the same
activity as the web app's remove-relation.
"""

import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.api.views.issue import IssueRelationListCreateAPIEndpoint
from plane.app.serializers import IssueRelationSerializer
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueRelation, WorkspaceMember
from plane.utils.host import base_host

# stored type -> the same relation seen from the other work item
INVERSE = {"blocked_by": "blocking", "start_before": "start_after", "finish_before": "finish_after"}
DEPENDENCY_KEYS = ("blocking", "blocked_by", "start_before", "start_after", "finish_before", "finish_after")
DEPENDENCY_STORED = ("blocked_by", "start_before", "finish_before")
CUSTOM_KEYS = ("relates_to", "duplicate")
UUID_FIELDS = ("id", "project_id", "state_id", "type_id")


def remove_relations(request, slug, project_id, issue_id, related_id, stored_types=None):
    """Delete the relation(s) between two work items, either direction. 404 when there is none."""
    if not Issue.objects.filter(pk=issue_id, project_id=project_id, workspace__slug=slug).exists():
        return Response({"error": "Work item not found."}, status=status.HTTP_404_NOT_FOUND)
    rows = IssueRelation.objects.filter(workspace__slug=slug).filter(
        Q(issue_id=issue_id, related_issue_id=related_id) | Q(issue_id=related_id, related_issue_id=issue_id)
    )
    if stored_types is not None:
        rows = rows.filter(relation_type__in=stored_types)
    rows = list(rows)
    if not rows:
        return Response({"error": "Relation not found."}, status=status.HTTP_404_NOT_FOUND)
    for row in rows:
        current_instance = json.dumps(IssueRelationSerializer(row).data, cls=DjangoJSONEncoder)
        mine = str(row.issue_id) == str(issue_id)
        relation_type = row.relation_type if mine else INVERSE.get(row.relation_type, row.relation_type)
        row.delete()
        issue_activity.delay(
            type="issue_relation.activity.deleted",
            requested_data=json.dumps({"related_issue": str(related_id), "relation_type": relation_type}),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=current_instance,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


class _Relations(IssueRelationListCreateAPIEndpoint):
    """Upstream's list/create with its permission (project member; guests read only)."""

    keys = ()

    def get(self, request, slug, project_id, issue_id):
        """Upstream lists {project_id, issue_id}; the SDK reads work items (id, name, ...) with relation_type."""
        res = super().get(request, slug, project_id, issue_id)
        if res.status_code != 200:
            return res
        groups = {k: res.data.get(k, []) for k in self.keys}
        ids = {r["issue_id"] for rows in groups.values() for r in rows}
        found = {
            str(i["id"]): i
            for i in Issue.objects.filter(pk__in=ids, workspace__slug=slug).values(
                "id", "name", "sequence_id", "project_id", "state_id", "priority", "type_id", "sort_order"
            )
        }
        res.data = {
            k: [
                {
                    **{f: (str(v) if f in UUID_FIELDS and v else v) for f, v in found[r["issue_id"]].items()},
                    **r,
                    "relation_type": k,
                }
                for r in rows
                if r["issue_id"] in found
            ]
            for k, rows in groups.items()
        }
        return res


class WorkItemDependenciesAPIEndpoint(_Relations):
    keys = DEPENDENCY_KEYS

    def post(self, request, slug, project_id, issue_id):
        """The SDK sends {relation_type, work_item_ids}; upstream reads {relation_type, issues}."""
        if request.data.get("relation_type") not in DEPENDENCY_KEYS:
            return Response(
                {"relation_type": f"Use one of: {', '.join(DEPENDENCY_KEYS)}."}, status=status.HTTP_400_BAD_REQUEST
            )
        if isinstance(request.data, QueryDict):  # form bodies are immutable; the SDK sends JSON
            return Response({"error": "Send a JSON body."}, status=status.HTTP_400_BAD_REQUEST)
        if "work_item_ids" in request.data:
            request.data["issues"] = request.data.pop("work_item_ids")
        return super().post(request, slug, project_id, issue_id)


class WorkItemDependencyDetailAPIEndpoint(IssueRelationListCreateAPIEndpoint):
    def delete(self, request, slug, project_id, issue_id, related_id):
        return remove_relations(request, slug, project_id, issue_id, related_id, DEPENDENCY_STORED)


class WorkItemCustomRelationsAPIEndpoint(_Relations):
    keys = CUSTOM_KEYS


class WorkItemCustomRelationDetailAPIEndpoint(IssueRelationListCreateAPIEndpoint):
    def delete(self, request, slug, project_id, issue_id, related_id):
        # The MCP's delete defaults to this route, so it removes every relation between the two, any type.
        return remove_relations(request, slug, project_id, issue_id, related_id)


class WorkItemRelationRemoveAPIEndpoint(IssueRelationListCreateAPIEndpoint):
    def post(self, request, slug, project_id, issue_id):
        try:
            related_id = uuid.UUID(str(request.data.get("related_issue")))
        except ValueError:
            return Response({"related_issue": "A work item id is required."}, status=status.HTTP_400_BAD_REQUEST)
        return remove_relations(request, slug, project_id, issue_id, related_id)


class WorkspaceMemberOnly(BasePermission):
    def has_permission(self, request, view):
        return (
            not request.user.is_anonymous
            and WorkspaceMember.objects.filter(
                workspace__slug=view.kwargs["slug"], member=request.user, is_active=True
            ).exists()
        )


class RelationDefinitionsAPIEndpoint(BaseAPIView):
    permission_classes = [WorkspaceMemberOnly]

    def get(self, request, slug):
        """CE has no custom relation definitions; built-in types go in relation_type."""
        return Response(
            {
                "grouped_by": None,
                "sub_grouped_by": None,
                "total_count": 0,
                "next_cursor": "",
                "prev_cursor": "",
                "next_page_results": False,
                "prev_page_results": False,
                "count": 0,
                "total_pages": 0,
                "total_results": 0,
                "extra_stats": None,
                "results": [],
            }
        )
