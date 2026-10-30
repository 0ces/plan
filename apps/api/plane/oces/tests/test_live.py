# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

import pytest

from plane.db.models import Issue, ProjectMember, User, WorkspaceMember
from plane.oces import live

from .test_work_item_types import make_project


class FakeRedis:
    def __init__(self):
        self.sent = []

    def publish(self, channel, message):
        self.sent.append((channel, json.loads(message)))


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(live, "redis_instance", lambda: fake)
    return fake


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "LV")


def base(project):
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}"


@pytest.mark.contract
class TestEvents:
    def test_create_and_update_publish_ids_only(self, session_client, project, redis):
        res = session_client.post(f"{base(project)}/issues/", {"name": "secret title"}, format="json")
        assert res.status_code == 201
        issue_id = res.json()["id"]
        session_client.patch(f"{base(project)}/issues/{issue_id}/", {"priority": "high"}, format="json")

        channels = {c for c, _ in redis.sent}
        assert channels == {f"oces:live:{project.workspace.slug}"}
        events = [e for _, e in redis.sent if e["action"] in ("post", "patch")]
        assert events[0]["project_id"] == str(project.id) and events[0]["issue_id"] == issue_id
        assert events[1]["issue_id"] == issue_id and events[1]["action"] == "patch"
        assert "secret title" not in json.dumps(redis.sent)

    def test_nested_issue_routes_carry_issue_id(self, session_client, project, redis, create_user):
        issue = Issue.objects.create(name="x", project=project, workspace=project.workspace, created_by=create_user)
        res = session_client.post(
            f"{base(project)}/issues/{issue.id}/comments/", {"comment_html": "<p>hi</p>"}, format="json"
        )
        assert res.status_code == 201
        assert any(e["issue_id"] == str(issue.id) and e["action"] == "post" for _, e in redis.sent)

    def test_reads_failures_and_personal_settings_publish_nothing(self, session_client, project, redis):
        session_client.get(f"{base(project)}/issues/")
        session_client.post(f"{base(project)}/issues/", {"name": ""}, format="json")  # 400
        session_client.post(
            f"{base(project)}/user-properties/", {"display_filters": {"layout": "kanban"}}, format="json"
        )
        assert [e for _, e in redis.sent if e["action"] != "activity"] == []

    def test_public_api_writes_publish(self, api_key_client, project, redis):
        res = api_key_client.post(
            f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/work-items/",
            {"name": "from mcp"},
            format="json",
        )
        assert res.status_code == 201
        assert any(e["project_id"] == str(project.id) and e["action"] == "post" for _, e in redis.sent)

    def test_activity_task_publishes(self, project, redis, create_user):
        issue = Issue.objects.create(name="x", project=project, workspace=project.workspace, created_by=create_user)

        class Task:
            name = live.ACTIVITY_TASK

        live.activity_written(
            sender=Task, kwargs={"project_id": str(project.id), "issue_id": str(issue.id), "actor_id": "u"}
        )
        assert redis.sent == [
            (
                f"oces:live:{project.workspace.slug}",
                {"project_id": str(project.id), "issue_id": str(issue.id), "action": "activity"},
            )
        ]

    def test_redis_down_does_not_break_writes(self, session_client, project, monkeypatch):
        def boom():
            raise ConnectionError("redis down")

        monkeypatch.setattr(live, "redis_instance", boom)
        res = session_client.post(f"{base(project)}/issues/", {"name": "still saved"}, format="json")
        assert res.status_code == 201


@pytest.mark.contract
class TestAccess:
    def test_member_gets_their_projects_only(self, session_client, project, workspace, create_user):
        other_owner = User.objects.create(email="x@example.com", username="x")
        WorkspaceMember.objects.create(workspace=workspace, member=other_owner, role=20)
        hidden = make_project(workspace, other_owner, "HD")
        ProjectMember.objects.filter(project=hidden, member=create_user).delete()

        res = session_client.get(f"/api/workspaces/{workspace.slug}/oces/live-access/")
        assert res.status_code == 200
        body = res.json()
        assert body["user_id"] == str(create_user.id)
        assert str(project.id) in body["project_ids"] and str(hidden.id) not in body["project_ids"]

    def test_outsider_is_refused(self, api_client, workspace, db):
        outsider = User.objects.create(email="out@example.com", username="out")
        api_client.force_authenticate(user=outsider)
        res = api_client.get(f"/api/workspaces/{workspace.slug}/oces/live-access/")
        assert res.status_code == 403
