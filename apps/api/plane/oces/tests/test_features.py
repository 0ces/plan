# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember, User, WorkspaceMember
from plane.oces.features import PROJECT_KEYS, WORKSPACE_KEYS


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Fork", identifier="FK", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def guest_client(db, workspace, project, api_client):
    guest = User.objects.create(email="guest@example.com", username="guest")
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
    ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
    api_client.force_authenticate(user=guest)
    return api_client


def ws_url(slug, internal=False):
    return f"/api/workspaces/{slug}/oces/features/" if internal else f"/api/v1/workspaces/{slug}/features/"


def project_url(slug, project_id, internal=False):
    base = f"/api/workspaces/{slug}/projects/{project_id}"
    return f"{base}/oces/features/" if internal else f"/api/v1{base[4:]}/features/"


@pytest.mark.contract
class TestWorkspaceFeatures:
    def test_get_returns_every_official_key_false(self, api_key_client, workspace):
        res = api_key_client.get(ws_url(workspace.slug))
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == {key: False for key in WORKSPACE_KEYS}

    def test_unbuilt_feature_cannot_be_enabled(self, api_key_client, workspace):
        res = api_key_client.patch(ws_url(workspace.slug), {"initiatives": True}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.json()["code"] == "feature_not_available"

    def test_disable_is_allowed_and_stored(self, api_key_client, workspace):
        res = api_key_client.patch(ws_url(workspace.slug), {"initiatives": False, "teams": False}, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert workspace.oces_features.initiatives is False

    def test_rejects_unknown_and_non_bool(self, api_key_client, workspace):
        assert api_key_client.patch(ws_url(workspace.slug), {"nope": True}, format="json").status_code == 400
        assert api_key_client.patch(ws_url(workspace.slug), {"initiatives": "yes"}, format="json").status_code == 400

    def test_internal_route_uses_session(self, session_client, workspace):
        assert session_client.get(ws_url(workspace.slug, internal=True)).status_code == status.HTTP_200_OK

    def test_non_admin_cannot_patch(self, guest_client, workspace):
        assert guest_client.get(ws_url(workspace.slug, internal=True)).status_code == status.HTTP_200_OK
        res = guest_client.patch(ws_url(workspace.slug, internal=True), {"initiatives": False}, format="json")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_requires_auth(self, api_client, workspace):
        assert api_client.get(ws_url(workspace.slug)).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.contract
class TestProjectFeatures:
    def test_get_maps_upstream_columns(self, api_key_client, workspace, project):
        project.module_view = True
        project.save()
        res = api_key_client.get(project_url(workspace.slug, project.id))
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert set(body) == set(PROJECT_KEYS)
        assert body["modules"] is True and body["epics"] is False

    def test_patch_upstream_feature_writes_project(self, api_key_client, workspace, project):
        res = api_key_client.patch(project_url(workspace.slug, project.id), {"cycles": True}, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["cycles"] is True
        project.refresh_from_db()
        assert project.cycle_view is True

    def test_work_item_types_not_available_yet(self, api_key_client, workspace, project):
        res = api_key_client.patch(project_url(workspace.slug, project.id), {"work_item_types": True}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        project.refresh_from_db()
        assert project.is_issue_type_enabled is False

    def test_guest_reads_but_cannot_patch(self, guest_client, workspace, project):
        url = project_url(workspace.slug, project.id, internal=True)
        assert guest_client.get(url).status_code == status.HTTP_200_OK
        assert guest_client.patch(url, {"cycles": True}, format="json").status_code == status.HTTP_403_FORBIDDEN

    def test_project_from_other_workspace_is_404(self, api_key_client, workspace, project):
        res = api_key_client.get(f"/api/v1/workspaces/other/projects/{project.id}/features/")
        assert res.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
