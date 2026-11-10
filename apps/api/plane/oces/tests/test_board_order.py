# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import State

from .test_work_item_types import make_project
from .test_worklogs import person


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "BO")


def url(project):
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/oces/board-order/"


@pytest.mark.contract
class TestBoardOrder:
    def test_save_read_reset(self, session_client, project):
        todo = State.objects.get(project=project)
        done = State.objects.create(name="Done", project=project, workspace=project.workspace, group="completed")
        assert session_client.get(url(project)).json() == {"state_ids": []}
        order = [str(done.id), str(todo.id)]
        assert session_client.put(url(project), {"state_ids": order}, format="json").status_code == 200
        assert session_client.get(url(project)).json() == {"state_ids": order}
        assert session_client.put(url(project), {"state_ids": []}, format="json").json() == {"state_ids": []}

    def test_validation(self, session_client, project, workspace, create_user):
        other = State.objects.get(project=make_project(workspace, create_user, "XX"))
        for body in ({}, {"state_ids": "x"}, {"state_ids": [str(other.id)]}):
            assert session_client.put(url(project), body, format="json").status_code == 400, body
        todo = str(State.objects.get(project=project).id)
        assert session_client.put(url(project), {"state_ids": [todo, todo]}, format="json").status_code == 400

    def test_members_read_admins_write(self, project):
        _, member = person(project, "m@oces.test", 15)
        assert member.get(url(project)).status_code == 200
        assert member.put(url(project), {"state_ids": []}, format="json").status_code == 403
