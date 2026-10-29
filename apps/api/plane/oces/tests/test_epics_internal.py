# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Issue, ProjectMember, State, User, WorkspaceMember
from plane.oces.work_item_types import enable_project_types, project_types

from .test_work_item_types import make_project


@pytest.fixture
def project(db, workspace, create_user):
    project = make_project(workspace, create_user, "EP")
    enable_project_types(project)
    return project


def tid(project, name):
    return str(project_types(project.id).get(name=name).id)


def base(project):
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}"


@pytest.mark.contract
class TestInternalWorkItemType:
    def test_web_create_keeps_type_id_and_lists_return_it(self, session_client, project):
        bug = tid(project, "Bug")
        res = session_client.post(f"{base(project)}/issues/", {"name": "x", "type_id": bug}, format="json")
        assert res.status_code == 201, res.json()
        assert str(res.json()["type_id"]) == bug
        listed = session_client.get(f"{base(project)}/issues/").json()
        rows = listed["results"] if isinstance(listed, dict) else listed
        assert any(str(r.get("type_id")) == bug for r in rows)

    def test_web_create_rejects_foreign_type(self, session_client, project, workspace, create_user):
        other = make_project(workspace, create_user, "EQ")
        enable_project_types(other)
        res = session_client.post(
            f"{base(project)}/issues/", {"name": "y", "type_id": tid(other, "Bug")}, format="json"
        )
        assert res.status_code == 400

    def test_internal_type_list(self, session_client, project):
        res = session_client.get(f"{base(project)}/oces/work-item-types/")
        assert res.status_code == 200 and len(res.json()) == 4


@pytest.mark.contract
class TestEpicProgress:
    def test_list_and_progress(self, session_client, project, create_user):
        done = State.objects.create(name="Done", project=project, workspace=project.workspace, group="completed")
        epic = Issue.objects.create(
            name="E", project=project, workspace=project.workspace, type_id=tid(project, "Epic")
        )
        Issue.objects.create(name="c1", project=project, workspace=project.workspace, parent=epic, state=done)
        Issue.objects.create(name="c2", project=project, workspace=project.workspace, parent=epic)
        body = session_client.get(f"{base(project)}/oces/epics/").json()
        assert [e["name"] for e in body] == ["E"]
        progress = body[0]["progress"]
        assert progress["total_issues"] == 2 and progress["completed_issues"] == 1 and progress["backlog_issues"] == 1
        res = session_client.get(f"{base(project)}/oces/epics/{epic.id}/progress/")
        assert res.json()["completed_issues"] == 1

    def test_limited_guest_sees_only_own(self, api_client, project, workspace):
        Issue.objects.create(name="E", project=project, workspace=project.workspace, type_id=tid(project, "Epic"))
        guest = User.objects.create(email="g2@example.com", username="g2")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
        api_client.force_authenticate(user=guest)
        assert api_client.get(f"{base(project)}/oces/epics/").json() == []
