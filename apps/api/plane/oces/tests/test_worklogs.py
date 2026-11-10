# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date

import pytest
from rest_framework.test import APIClient

from plane.db.models import Issue, ProjectMember, User, WorkspaceMember

from .test_work_item_types import make_project


@pytest.fixture
def project(db, workspace, create_user):
    p = make_project(workspace, create_user, "TT")
    p.is_time_tracking_enabled = True
    p.save()
    return p


@pytest.fixture
def item(project, create_user):
    return Issue.objects.create(name="Story", project=project, workspace=project.workspace, created_by=create_user)


def person(project, email, role):
    u = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=project.workspace, member=u, role=role)
    ProjectMember.objects.create(project=project, member=u, role=role, is_active=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return u, c


def url(project, path):
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def logs(project, item, log_id=None):
    return url(project, f"work-items/{item.id}/worklogs/" + (f"{log_id}/" if log_id else ""))


@pytest.mark.contract
class TestWorkLogs:
    def test_crud_summary_and_timesheet(self, api_key_client, project, item, create_user):
        res = api_key_client.post(logs(project, item), {"duration": 90, "description": "Spike"}, format="json")
        assert res.status_code == 201, res.content
        log = res.json()
        assert log["duration"] == 90 and log["logged_by"] == str(create_user.id) and log["logged_at"]
        res = api_key_client.post(logs(project, item), {"duration": 30, "logged_at": "2026-11-02"}, format="json")
        assert res.status_code == 201

        # the SDK reads the list as a plain array
        listed = api_key_client.get(logs(project, item)).json()
        assert isinstance(listed, list) and len(listed) == 2

        res = api_key_client.patch(logs(project, item, log["id"]), {"duration": 60}, format="json")
        assert res.json()["duration"] == 60 and res.json()["description"] == "Spike"

        summary = api_key_client.get(url(project, "worklogs/summary/")).json()
        assert summary == [{"work_item_id": str(item.id), "duration": 90}]

        sheet = api_key_client.get(url(project, "worklogs/?from=2026-11-01&to=2026-11-07")).json()
        assert [r["duration"] for r in sheet["results"]] == [30]
        assert sheet["results"][0]["work_item"]["name"] == "Story"

        assert api_key_client.delete(logs(project, item, log["id"])).status_code == 204
        assert len(api_key_client.get(logs(project, item)).json()) == 1

    def test_validation(self, api_key_client, project, item):
        for body in ({}, {"duration": 0}, {"duration": 1441}, {"duration": "60"}, {"duration": True}):
            assert api_key_client.post(logs(project, item), body, format="json").status_code == 400, body
        bad_date = {"duration": 5, "logged_at": "yesterday"}
        assert api_key_client.post(logs(project, item), bad_date, format="json").status_code == 400
        assert api_key_client.get(url(project, "worklogs/?from=2026-11-07&to=2026-11-01")).status_code == 400
        assert api_key_client.get(url(project, "worklogs/?logged_by=nope")).status_code == 400

    def test_switch_off_blocks_writes(self, api_key_client, project, item):
        project.is_time_tracking_enabled = False
        project.save()
        res = api_key_client.post(logs(project, item), {"duration": 15}, format="json")
        assert res.status_code == 400 and res.json()["code"] == "time_tracking_disabled"
        assert api_key_client.get(logs(project, item)).status_code == 200

    def test_permissions(self, api_key_client, project, item):
        mine = api_key_client.post(logs(project, item), {"duration": 20}, format="json").json()
        _, member = person(project, "member@oces.test", 15)
        _, guest = person(project, "guest@oces.test", 5)

        # guests neither see nor log time
        assert guest.get(logs(project, item)).status_code == 403
        assert guest.post(logs(project, item), {"duration": 5}, format="json").status_code == 403

        # members log their own time but cannot change someone else's
        theirs = member.post(logs(project, item), {"duration": 10}, format="json")
        assert theirs.status_code == 201
        assert member.patch(logs(project, item, mine["id"]), {"duration": 1}, format="json").status_code == 403
        assert member.delete(logs(project, item, mine["id"])).status_code == 403
        assert (
            member.patch(logs(project, item, theirs.json()["id"]), {"duration": 11}, format="json").status_code == 200
        )

        # the project admin can change anyone's entry
        res = api_key_client.patch(logs(project, item, theirs.json()["id"]), {"duration": 12}, format="json")
        assert res.status_code == 200

    def test_deleted_work_item_drops_out(self, api_key_client, project, item):
        api_key_client.post(logs(project, item), {"duration": 45, "logged_at": date.today().isoformat()}, format="json")
        item.delete()
        assert api_key_client.get(url(project, "worklogs/summary/")).json() == []
        assert api_key_client.get(url(project, "worklogs/")).json()["results"] == []

    def test_internal_route(self, session_client, project, item):
        base = f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/oces"
        res = session_client.post(f"{base}/work-items/{item.id}/worklogs/", {"duration": 25}, format="json")
        assert res.status_code == 201, res.content
        assert session_client.get(f"{base}/worklogs/summary/").json()[0]["duration"] == 25
