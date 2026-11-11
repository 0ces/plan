# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest

from plane.db.models import Issue, IssueActivity, IssueRelation, User, Workspace, WorkspaceMember
from rest_framework.test import APIClient

from .test_work_item_types import make_project
from .test_worklogs import person, url


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "RL")


@pytest.fixture
def items(project, create_user):
    return [
        Issue.objects.create(name=f"Item {i}", project=project, workspace=project.workspace, created_by=create_user)
        for i in range(3)
    ]


def relate(project, a, b, relation_type):
    return IssueRelation.objects.create(
        issue=a, related_issue=b, relation_type=relation_type, project=project, workspace=project.workspace
    )


def wi(project, item, path):
    return url(project, f"work-items/{item.id}/{path}")


@pytest.mark.contract
class TestRelationDelete:
    def test_dependency_route_from_either_side(self, api_key_client, project, items):
        a, b, c = items
        relate(project, a, b, "blocked_by")  # a blocked by b
        relate(project, c, a, "blocked_by")  # a blocking c
        # from the side that holds the row
        res = api_key_client.delete(wi(project, a, f"dependencies/{b.id}/"))
        assert res.status_code == 204, res.content
        # from the other side (the row is stored on c)
        res = api_key_client.delete(wi(project, a, f"dependencies/{c.id}/"))
        assert res.status_code == 204, res.content
        assert not IssueRelation.objects.filter(issue__in=items).exists()

    def test_dependency_route_skips_relates_to(self, api_key_client, project, items):
        a, b, _ = items
        relate(project, a, b, "relates_to")
        assert api_key_client.delete(wi(project, a, f"dependencies/{b.id}/")).status_code == 404
        assert IssueRelation.objects.filter(issue=a).exists()

    def test_custom_route_removes_any_type(self, api_key_client, project, items):
        a, b, c = items
        relate(project, b, a, "blocked_by")
        relate(project, a, c, "relates_to")
        assert api_key_client.delete(wi(project, a, f"work-item-relations/{b.id}/")).status_code == 204
        assert api_key_client.delete(wi(project, c, f"work-item-relations/{a.id}/")).status_code == 204
        assert not IssueRelation.objects.filter(issue__in=items).exists()

    def test_sdk_remove_route(self, api_key_client, project, items):
        a, b, _ = items
        relate(project, a, b, "duplicate")
        # plane-sdk posts without the trailing slash
        res = api_key_client.post(wi(project, a, "relations/remove"), {"related_issue": str(b.id)}, format="json")
        assert res.status_code == 204, res.content
        assert not IssueRelation.objects.filter(issue=a).exists()
        res = api_key_client.post(wi(project, a, "relations/remove/"), {"related_issue": "nope"}, format="json")
        assert res.status_code == 400

    def test_unknown_relation_404(self, api_key_client, project, items):
        a, b, _ = items
        assert api_key_client.delete(wi(project, a, f"dependencies/{b.id}/")).status_code == 404
        assert api_key_client.delete(wi(project, a, f"work-item-relations/{uuid.uuid4()}/")).status_code == 404
        missing = url(project, f"work-items/{uuid.uuid4()}/work-item-relations/{b.id}/")
        assert api_key_client.delete(missing).status_code == 404

    def test_activity_written(self, api_key_client, project, items):
        a, b, _ = items
        relate(project, a, b, "blocked_by")
        assert api_key_client.delete(wi(project, b, f"dependencies/{a.id}/")).status_code == 204
        mine = IssueActivity.objects.get(issue=b, verb="deleted")
        assert mine.field == "blocking" and mine.old_identifier == a.id
        theirs = IssueActivity.objects.get(issue=a, verb="deleted")
        assert theirs.field == "blocked_by"

    def test_permissions(self, project, items, create_user):
        a, b, _ = items
        relate(project, a, b, "blocked_by")
        _, guest = person(project, "guest@rl.test", 5)
        assert guest.delete(wi(project, a, f"dependencies/{b.id}/")).status_code == 403
        assert guest.post(wi(project, a, "relations/remove/"), {"related_issue": str(b.id)}).status_code == 403

        stranger = User.objects.create(email="x@other.test", username="xother")
        other = Workspace.objects.create(name="Other", slug="other-rl", owner=stranger)
        WorkspaceMember.objects.create(workspace=other, member=stranger, role=20)
        c = APIClient()
        c.force_authenticate(user=stranger)
        assert c.delete(wi(project, a, f"work-item-relations/{b.id}/")).status_code == 403
        assert IssueRelation.objects.filter(issue=a).exists()


@pytest.mark.contract
class TestRelationListCreate:
    def test_dependencies_list_and_create(self, api_key_client, project, items):
        a, b, c = items
        res = api_key_client.post(
            wi(project, a, "dependencies/"), {"relation_type": "blocking", "work_item_ids": [str(b.id)]}, format="json"
        )
        assert res.status_code == 201, res.content
        assert IssueRelation.objects.filter(issue=b, related_issue=a, relation_type="blocked_by").exists()
        relate(project, a, c, "relates_to")
        listed = api_key_client.get(wi(project, a, "dependencies/")).json()
        assert set(listed) == {"blocking", "blocked_by", "start_before", "start_after", "finish_before", "finish_after"}
        assert listed["blocking"][0]["id"] == str(b.id) and listed["blocking"][0]["name"] == b.name
        custom = api_key_client.get(wi(project, a, "work-item-relations/")).json()
        assert custom["duplicate"] == [] and len(custom["relates_to"]) == 1
        row = custom["relates_to"][0]
        assert row["id"] == row["issue_id"] == str(c.id) and row["name"] == c.name
        c.refresh_from_db()
        assert row["relation_type"] == "relates_to" and row["sequence_id"] == c.sequence_id
        bad = api_key_client.post(
            wi(project, a, "dependencies/"),
            {"relation_type": "relates_to", "work_item_ids": [str(c.id)]},
            format="json",
        )
        assert bad.status_code == 400

    def test_definitions_empty_page(self, api_key_client, project):
        res = api_key_client.get(f"/api/v1/workspaces/{project.workspace.slug}/work-item-relation-definitions/")
        assert res.status_code == 200 and res.json()["results"] == [] and res.json()["next_page_results"] is False
