# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Issue, ProjectMember, State, User, WorkspaceMember

from .test_work_item_types import make_project


@pytest.fixture
def ws(workspace):
    return f"/api/v1/workspaces/{workspace.slug}/initiatives/"


@pytest.fixture
def setup(db, workspace, create_user):
    """Project A (2 open, 1 done), project B (1 open), a hidden project H the user is not in."""
    a = make_project(workspace, create_user, "IA")
    b = make_project(workspace, create_user, "IB")
    owner = User.objects.create(email="h@example.com", username="h")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20)
    h = make_project(workspace, owner, "IH")
    ProjectMember.objects.filter(project=h, member=create_user).delete()
    done = State.objects.create(name="Done", project=a, workspace=workspace, group="completed")

    def item(project, name, **kw):
        return Issue.objects.create(name=name, project=project, workspace=workspace, created_by=create_user, **kw)

    return {
        "a": a,
        "b": b,
        "h": h,
        "a1": item(a, "a1"),
        "a2": item(a, "a2"),
        "a3": item(a, "a3", state=done),
        "b1": item(b, "b1"),
        "h1": item(h, "h1"),
    }


def create(client, ws, **body):
    res = client.post(ws, {"name": "Launch", **body}, format="json")
    assert res.status_code == 201, res.content
    return res.json()


@pytest.mark.contract
class TestInitiatives:
    def test_crud_and_shape(self, api_key_client, ws, create_user):
        made = create(
            api_key_client,
            ws,
            description_html="<p>Ship <b>v2</b><script>x</script></p>",
            start_date="2026-11-01",
            end_date="2026-12-01",
            state="PLANNED",
            lead=str(create_user.id),
        )
        assert made["logo_props"] == {} and made["state"] == "PLANNED" and made["lead"] == str(create_user.id)
        assert "script" not in made["description_html"] and made["description_stripped"] == "Ship v2"
        listed = api_key_client.get(ws).json()
        assert [i["id"] for i in listed["results"]] == [made["id"]]
        url = f"{ws}{made['id']}/"
        assert api_key_client.patch(url, {"state": "ACTIVE"}, format="json").json()["state"] == "ACTIVE"
        assert api_key_client.get(url).json()["name"] == "Launch"
        assert api_key_client.delete(url).status_code == 204
        assert api_key_client.get(url).status_code == 404

    @pytest.mark.parametrize(
        "body, key",
        [
            ({"name": ""}, "name"),
            ({"name": "x", "state": "DONE"}, "state"),
            ({"name": "x", "start_date": "2026-12-01", "end_date": "2026-11-01"}, "end_date"),
            ({"name": "x", "start_date": "soon"}, "start_date"),
            ({"name": "x", "lead": "00000000-0000-0000-0000-000000000000"}, "lead"),
        ],
    )
    def test_validation(self, api_key_client, ws, body, key):
        res = api_key_client.post(ws, body, format="json")
        assert res.status_code == 400 and key in res.json()

    def test_projects_and_work_items_links(self, api_key_client, ws, setup):
        init = create(api_key_client, ws)
        projects = f"{ws}{init['id']}/projects/"
        res = api_key_client.post(projects, {"project_ids": [str(setup["a"].id)]}, format="json")
        assert res.status_code == 201 and [p["id"] for p in res.json()] == [str(setup["a"].id)]
        # a project the caller is not a member of is refused
        bad = api_key_client.post(projects, {"project_ids": [str(setup["h"].id)]}, format="json")
        assert bad.status_code == 400
        envelope = api_key_client.get(projects).json()
        assert envelope["total_results"] == 1 and envelope["results"][0]["identifier"] == "IA"
        assert api_key_client.delete(projects, {"project_ids": [str(setup["a"].id)]}, format="json").status_code == 204
        assert api_key_client.get(projects).json()["results"] == []

        items = f"{ws}{init['id']}/work-items/"
        res = api_key_client.post(items, {"work_item_ids": [str(setup["b1"].id)]}, format="json")
        assert res.status_code == 201 and res.json()[0]["id"] == str(setup["b1"].id)
        assert api_key_client.post(items, {"work_item_ids": [str(setup["h1"].id)]}, format="json").status_code == 400
        assert [r["name"] for r in api_key_client.get(items).json()["results"]] == ["b1"]
        assert api_key_client.delete(items, {"work_item_ids": [str(setup["b1"].id)]}, format="json").status_code == 204
        assert api_key_client.get(items).json()["results"] == []

    def test_progress_rolls_up_without_duplicates(self, session_client, api_key_client, ws, setup, workspace):
        init = create(api_key_client, ws)
        base = f"{ws}{init['id']}"
        epic = Issue.objects.create(
            name="epic", project=setup["b"], workspace=workspace, created_by=setup["b1"].created_by
        )
        setup["b1"].parent = epic
        setup["b1"].save()
        api_key_client.post(f"{base}/projects/", {"project_ids": [str(setup["a"].id)]}, format="json")
        api_key_client.post(f"{base}/epics/", {"epic_ids": [str(epic.id)]}, format="json")
        # a1 is already covered by project A: still counted once
        api_key_client.post(f"{base}/work-items/", {"work_item_ids": [str(setup["a1"].id)]}, format="json")
        internal = f"/api/workspaces/{workspace.slug}/oces/initiatives/{init['id']}/"
        body = session_client.get(internal).json()
        p = body["progress"]
        assert (p["total_issues"], p["backlog_issues"], p["completed_issues"]) == (4, 3, 1)
        assert body["epic_ids"] == [str(epic.id)] and body["work_item_ids"] == [str(setup["a1"].id)]

    def test_labels(self, api_key_client, ws):
        init = create(api_key_client, ws)
        label = api_key_client.post(f"{ws}labels/", {"name": "Q4", "color": "#f00"}, format="json").json()
        assert api_key_client.post(f"{ws}labels/", {"name": "q4"}, format="json").status_code == 400
        links = f"{ws}{init['id']}/labels/"
        assert api_key_client.post(links, {"label_ids": [label["id"]]}, format="json").status_code == 201
        assert [lb["name"] for lb in api_key_client.get(links).json()["results"]] == ["Q4"]
        assert api_key_client.get(f"{ws}{init['id']}/").json()["label_ids"] == [label["id"]]
        assert api_key_client.delete(f"{ws}labels/{label['id']}/").status_code == 204
        assert api_key_client.get(links).json()["results"] == []

    def test_guests_and_outsiders_are_refused(self, api_client, api_key_client, ws, workspace):
        create(api_key_client, ws)
        guest = User.objects.create(email="g@example.com", username="g")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        api_client.force_authenticate(user=guest)
        assert api_client.get(ws).status_code == 403
        outsider = User.objects.create(email="o@example.com", username="o")
        api_client.force_authenticate(user=outsider)
        assert api_client.get(ws).status_code == 403

    def test_only_admin_or_creator_deletes(self, api_client, api_key_client, ws, workspace):
        init = create(api_key_client, ws)
        member = User.objects.create(email="m@example.com", username="m")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        api_client.force_authenticate(user=member)
        assert api_client.patch(f"{ws}{init['id']}/", {"state": "ACTIVE"}, format="json").status_code == 200
        assert api_client.delete(f"{ws}{init['id']}/").status_code == 403

    def test_feature_can_be_switched_on(self, api_key_client, workspace):
        url = f"/api/v1/workspaces/{workspace.slug}/features/"
        assert api_key_client.patch(url, {"initiatives": True}, format="json").json()["initiatives"] is True
