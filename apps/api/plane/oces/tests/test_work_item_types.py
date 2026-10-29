# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Issue, Project, ProjectMember, State, User, WorkspaceMember
from plane.oces.work_item_types import enable_project_types, project_types


def make_project(workspace, user, identifier):
    project = Project.objects.create(name=identifier, identifier=identifier, workspace=workspace, created_by=user)
    ProjectMember.objects.create(project=project, member=user, role=20, is_active=True)
    State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    return project


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "TY")


@pytest.fixture
def typed_project(project):
    enable_project_types(project)
    return project


def types_url(project, type_id=None):
    url = f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/work-item-types/"
    return f"{url}{type_id}/" if type_id else url


def type_id(project, name):
    return str(project_types(project.id).get(name=name).id)


@pytest.mark.contract
class TestEnableTypes:
    def test_feature_switch_creates_defaults_and_types_old_items(self, api_key_client, project, create_user):
        old = Issue.objects.create(name="old", project=project, workspace=project.workspace, created_by=create_user)
        assert old.type_id is None
        url = f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/features/"
        res = api_key_client.patch(url, {"work_item_types": True}, format="json")
        assert res.status_code == 200 and res.json()["work_item_types"] is True
        names = sorted(project_types(project.id).values_list("name", flat=True))
        assert names == ["Bug", "Epic", "Feature", "Task"]
        old.refresh_from_db()
        assert old.type.name == "Task"
        # Switching on twice does not duplicate.
        api_key_client.patch(url, {"work_item_types": True}, format="json")
        assert project_types(project.id).count() == 4

    def test_create_refused_while_off(self, api_key_client, project):
        res = api_key_client.post(types_url(project), {"name": "Story"}, format="json")
        assert res.status_code == 400 and res.json()["code"] == "work_item_types_disabled"


@pytest.mark.contract
class TestTypeCrud:
    def test_list_is_plain_array_in_official_shape(self, api_key_client, typed_project):
        res = api_key_client.get(types_url(typed_project))
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body, list) and len(body) == 4
        task = next(t for t in body if t["name"] == "Task")
        epic = next(t for t in body if t["name"] == "Epic")
        assert task["is_default"] is True and epic["is_epic"] is True and epic["is_default"] is False
        assert task["project_ids"] == [str(typed_project.id)]

    def test_create_and_conflicts(self, api_key_client, typed_project):
        res = api_key_client.post(types_url(typed_project), {"name": "Story", "description": "x"}, format="json")
        assert res.status_code == 201 and res.json()["is_default"] is False
        assert api_key_client.post(types_url(typed_project), {"name": "story"}, format="json").status_code == 409
        res = api_key_client.post(types_url(typed_project), {"name": "Saga", "is_epic": True}, format="json")
        assert res.status_code == 400

    def test_default_rules(self, api_key_client, typed_project):
        bug, task, epic = (type_id(typed_project, n) for n in ("Bug", "Task", "Epic"))

        def patch(tid, body):
            return api_key_client.patch(types_url(typed_project, tid), body, format="json").status_code

        assert (
            api_key_client.patch(types_url(typed_project, task), {"is_default": False}, format="json").status_code
            == 400
        )
        assert (
            api_key_client.patch(types_url(typed_project, task), {"is_active": False}, format="json").status_code == 400
        )
        assert (
            api_key_client.patch(types_url(typed_project, epic), {"is_default": True}, format="json").status_code == 400
        )
        assert patch(bug, {"is_epic": True}) == 400
        res = api_key_client.patch(types_url(typed_project, bug), {"is_default": True}, format="json")
        assert res.status_code == 200 and res.json()["is_default"] is True
        assert api_key_client.get(types_url(typed_project, task)).json()["is_default"] is False

    def test_delete_rules(self, api_key_client, typed_project, create_user):
        feature = type_id(typed_project, "Feature")
        assert api_key_client.delete(types_url(typed_project, type_id(typed_project, "Task"))).status_code == 400
        Issue.objects.create(
            name="f", project=typed_project, workspace=typed_project.workspace, type_id=feature, created_by=create_user
        )
        res = api_key_client.delete(types_url(typed_project, feature))
        assert res.status_code == 400 and res.json()["in_use"] == 1
        assert api_key_client.delete(types_url(typed_project, type_id(typed_project, "Bug"))).status_code == 204
        assert project_types(typed_project.id).count() == 3

    def test_other_projects_type_is_404(self, api_key_client, typed_project, workspace, create_user):
        other = make_project(workspace, create_user, "OT")
        enable_project_types(other)
        assert api_key_client.get(types_url(typed_project, type_id(other, "Bug"))).status_code == 404

    def test_guest_reads_but_cannot_write(self, api_client, typed_project, workspace):
        guest = User.objects.create(email="g@example.com", username="g")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        ProjectMember.objects.create(project=typed_project, member=guest, role=5, is_active=True)
        api_client.force_authenticate(user=guest)
        assert api_client.get(types_url(typed_project)).status_code == 200
        assert api_client.post(types_url(typed_project), {"name": "X"}, format="json").status_code == 403


@pytest.mark.contract
class TestWorkItemType:
    def issues_url(self, project):
        return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/work-items/"

    def test_create_uses_default_or_given_type(self, api_key_client, typed_project):
        res = api_key_client.post(self.issues_url(typed_project), {"name": "a"}, format="json")
        assert res.status_code == 201, res.json()
        assert Issue.objects.get(pk=res.json()["id"]).type.name == "Task"
        bug = type_id(typed_project, "Bug")
        res = api_key_client.post(self.issues_url(typed_project), {"name": "b", "type_id": bug}, format="json")
        assert res.status_code == 201 and str(res.json()["type_id"]) == bug

    def test_type_from_other_project_is_rejected(self, api_key_client, typed_project, workspace, create_user):
        other = make_project(workspace, create_user, "OX")
        enable_project_types(other)
        res = api_key_client.post(
            self.issues_url(typed_project), {"name": "c", "type_id": type_id(other, "Bug")}, format="json"
        )
        assert res.status_code == 400

    def test_orm_create_gets_default_type(self, typed_project, create_user):
        issue = Issue.objects.create(name="d", project=typed_project, workspace=typed_project.workspace)
        assert issue.type.name == "Task"

    def test_project_without_types_stays_untyped(self, project):
        issue = Issue.objects.create(name="e", project=project, workspace=project.workspace)
        assert issue.type_id is None
