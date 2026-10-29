# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.utils import timezone

from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueLabel,
    IssueRelation,
    Label,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)
from plane.oces.pql import PQLError, parse_pql
from plane.oces.work_item_types import enable_project_types, project_types

from .test_work_item_types import make_project


@pytest.fixture
def data(db, workspace, create_user):
    """Project PQ with: epic E (PQ-1) -> children A (done, urgent, labelled), B (overdue, assigned);
    C standalone, blocked by A; D archived."""
    project = make_project(workspace, create_user, "PQ")
    enable_project_types(project)
    done = State.objects.create(name="Done", project=project, workspace=workspace, group="completed")
    started = State.objects.create(name="Doing", project=project, workspace=workspace, group="started")
    label = Label.objects.create(name="ui", project=project, workspace=workspace)
    epic_type = project_types(project.id).get(is_epic=True)

    def new(name, **kw):
        return Issue.objects.create(name=name, project=project, workspace=workspace, created_by=create_user, **kw)

    epic = new("Epic checkout", type=epic_type)
    a = new("Card form", parent=epic, state=done, priority="urgent")
    b = new("Address step", parent=epic, state=started, target_date=timezone.now().date() - timedelta(days=2))
    c = new("Receipt email")
    d = new("Old thing", archived_at=timezone.now().date(), state=done)
    IssueLabel.objects.create(issue=a, label=label, project=project, workspace=workspace)
    IssueAssignee.objects.create(issue=b, assignee=create_user, project=project, workspace=workspace)
    IssueRelation.objects.create(
        issue=c, related_issue=a, relation_type="blocked_by", project=project, workspace=workspace
    )
    return {"project": project, "epic": epic, "a": a, "b": b, "c": c, "d": d, "label": label, "user": create_user}


def names(data, pql, base=None):
    q = parse_pql(pql, data["user"], data["project"].workspace.slug, data["project"].id)
    qs = (base or Issue.issue_objects).filter(project=data["project"]).filter(q).distinct()
    return sorted(qs.values_list("name", flat=True))


@pytest.mark.unit
class TestParser:
    def test_fields_and_operators(self, data):
        assert names(data, 'priority = "urgent"') == ["Card form"]
        assert names(data, 'priority IN ("urgent","high")') == ["Card form"]
        assert names(data, "stateGroup IN closedStates()") == ["Card form"]
        assert names(data, 'title ~ "step"') == ["Address step"]
        assert names(data, f'label = "{data["label"].id}"') == ["Card form"]
        assert names(data, "assignee = currentUser()") == ["Address step"]
        assert "Address step" not in names(data, "hasNoAssignee()")
        assert names(data, "dueDate < today()") == ["Address step"]
        assert names(data, "dueDate BETWEEN (daysAgo(7), today())") == ["Address step"]
        assert names(data, "dueDate BETWEEN daysAgo(7) AND today()") == ["Address step"]
        assert names(data, f'id = "PQ-{data["a"].sequence_id}"') == ["Card form"]

    def test_logic_and_precedence(self, data):
        # NOT > AND > OR
        assert names(data, 'priority = "urgent" OR title ~ "receipt" AND isTopLevel()') == [
            "Card form",
            "Receipt email",
        ]
        assert names(data, 'NOT isTopLevel() AND NOT priority = "urgent"') == ["Address step"]
        assert names(data, '(priority = "urgent" OR title ~ "address") AND isSubWorkItem()') == [
            "Address step",
            "Card form",
        ]

    def test_predicates_and_relations(self, data):
        assert names(data, "isEpic()") == ["Epic checkout"]
        assert names(data, "isEpic() AND hasChildren()") == ["Epic checkout"]
        assert names(data, "isOverdue()") == ["Address step"]
        assert names(data, f'childOf("PQ-{data["epic"].sequence_id}")') == ["Address step", "Card form"]
        assert names(data, f'childOf("{data["epic"].id}")') == ["Address step", "Card form"]
        assert names(data, f'parentOf("PQ-{data["a"].sequence_id}")') == ["Epic checkout"]
        assert names(data, f'blockedBy("PQ-{data["a"].sequence_id}")') == ["Receipt email"]
        assert names(data, f'blocks("PQ-{data["c"].sequence_id}")') == ["Card form"]
        assert names(data, "isArchived()", base=Issue.objects) == ["Old thing"]

    @pytest.mark.parametrize(
        "pql",
        [
            "",
            "priority",
            'priority = "huge"',
            "nope = 1",
            'state = "not-a-uuid"',
            "dueDate > 5",
            'title IN ("a")',
            'cf["x"] = "y"',
            'milestone = "x"',
            'childOf("ZZ-99")',
            "isOverdue() AND isEpic() AND isTopLevel() AND hasChildren() AND isDraft() AND isIntake()",
            'priority = "urgent" AND',
            "unknownFn()",
        ],
    )
    def test_errors(self, data, pql):
        with pytest.raises(PQLError):
            parse_pql(pql, data["user"], data["project"].workspace.slug, data["project"].id)


@pytest.mark.contract
class TestEndpoints:
    def url(self, data, path):
        return f"/api/v1/workspaces/{data['project'].workspace.slug}/{path}"

    def test_project_list_with_pql(self, api_key_client, data):
        res = api_key_client.get(
            self.url(data, f"projects/{data['project'].id}/work-items/"),
            {"pql": f'childOf("PQ-{data["epic"].sequence_id}")'},
        )
        assert res.status_code == 200, res.json()
        body = res.json()
        assert sorted(r["name"] for r in body["results"]) == ["Address step", "Card form"]
        assert body["total_count"] == 2

    def test_project_list_without_pql_is_upstream(self, api_key_client, data):
        res = api_key_client.get(self.url(data, f"projects/{data['project'].id}/work-items/"))
        assert res.status_code == 200 and len(res.json()["results"]) == 4

    def test_bad_pql_is_400_with_pql_key(self, api_key_client, data):
        res = api_key_client.get(self.url(data, f"projects/{data['project'].id}/work-items/"), {"pql": "nope = 1"})
        assert res.status_code == 400 and "pql" in res.json()

    def test_create_still_works(self, api_key_client, data):
        res = api_key_client.post(
            self.url(data, f"projects/{data['project'].id}/work-items/"), {"name": "new"}, format="json"
        )
        assert res.status_code == 201

    def test_workspace_list_and_archived(self, api_key_client, data):
        res = api_key_client.get(self.url(data, "work-items/"), {"pql": "isEpic()"})
        assert [r["name"] for r in res.json()["results"]] == ["Epic checkout"]
        res = api_key_client.get(self.url(data, f"projects/{data['project'].id}/archived-work-items/"))
        assert [r["name"] for r in res.json()["results"]] == ["Old thing"]

    def test_count(self, api_key_client, data):
        project = data["project"]
        res = api_key_client.get(self.url(data, "work-items/count/"), {"pql": f'project = "{project.id}"'})
        assert res.json() == {"grouped_by": None, "sub_grouped_by": None, "total_count": 4, "grouped_counts": {}}
        res = api_key_client.get(
            self.url(data, "work-items/count/"),
            {"pql": f'project = "{project.id}"', "group_by": "state__group", "sub_group_by": "priority"},
        )
        body = res.json()
        assert body["total_count"] == 4
        assert body["grouped_counts"]["completed"] == {"count": 1, "sub_grouped_counts": {"urgent": {"count": 1}}}
        assert api_key_client.get(self.url(data, "work-items/count/"), {"group_by": "name"}).status_code == 400

    def test_outsider_sees_nothing(self, api_client, data, workspace):
        other = User.objects.create(email="o@example.com", username="o")
        WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
        api_client.force_authenticate(user=other)
        res = api_client.get(self.url(data, "work-items/"), {"pql": "isEpic()"})
        assert res.status_code == 200 and res.json()["results"] == []

    def test_limited_guest_sees_only_own(self, api_client, data, workspace):
        guest = User.objects.create(email="gq@example.com", username="gq")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        ProjectMember.objects.create(project=data["project"], member=guest, role=5, is_active=True)
        api_client.force_authenticate(user=guest)
        res = api_client.get(self.url(data, "work-items/count/"))
        assert res.json()["total_count"] == 0
