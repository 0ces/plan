# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64

import pytest

from plane.db.models import Issue, Page, ProjectMember, User, WorkspaceMember
from plane.oces import page_content
from plane.oces.page_content import LiveUnavailable

from .test_work_item_types import make_project

HTML = "<h2>Report</h2><p>See <a href='https://x.test'>x</a></p><script>alert(1)</script>"


@pytest.fixture(autouse=True)
def fake_live(monkeypatch):
    """Stand-in for the live server: records calls and echoes the HTML it got."""
    calls = []

    def render(page_id, name, html):
        calls.append({"page_id": str(page_id), "name": name, "html": html})
        return {
            "description_binary": b"yjs:" + html.encode(),
            "description_html": html,
            "description_json": {"type": "doc"},
        }

    monkeypatch.setattr("plane.oces.page_views.render", render)
    return calls


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "PG")


@pytest.fixture
def urls(workspace, project):
    ws = f"/api/v1/workspaces/{workspace.slug}"
    return {"ws": f"{ws}/pages/", "proj": f"{ws}/projects/{project.id}/pages/"}


def create(client, url, **body):
    res = client.post(url, {"name": "Runbook", "description_html": HTML, **body}, format="json")
    assert res.status_code == 201, res.content
    return res.json()


def member(workspace, project, email, ws_role=15, project_role=15):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=ws_role)
    if project_role:
        ProjectMember.objects.create(project=project, member=user, role=project_role, is_active=True)
    return user


@pytest.mark.contract
class TestPages:
    @pytest.mark.parametrize("scope", ["proj", "ws"])
    def test_crud(self, api_key_client, urls, scope, fake_live):
        made = create(api_key_client, urls[scope])
        # sanitized before conversion, stored as the editor document
        assert "<script>" not in fake_live[0]["html"] and fake_live[0]["name"] == "Runbook"
        page = Page.objects.get(pk=made["id"])
        assert bytes(page.description_binary).startswith(b"yjs:<h2>Report</h2>")
        assert page.description_stripped.startswith("Report")
        assert made["parent_id"] is None and made["collection_id"] is None
        assert (made["projects"] != []) == (scope == "proj")

        listed = api_key_client.get(urls[scope]).json()
        assert listed["total_results"] == 1 and listed["results"][0]["id"] == made["id"]

        one = f"{urls[scope]}{made['id']}/"
        res = api_key_client.put(one, {"description_html": "<p>v2</p>"}, format="json")
        assert res.status_code == 200 and res.json()["description_html"] == "<p>v2</p>"
        assert fake_live[-1]["page_id"] == made["id"]
        assert api_key_client.patch(one, {"name": "Renamed"}, format="json").json()["name"] == "Renamed"

        assert api_key_client.delete(one).status_code == 400  # archive first
        assert api_key_client.post(f"{one}archive/").status_code == 200
        assert api_key_client.put(one, {"name": "x"}, format="json").status_code == 400
        assert api_key_client.delete(f"{one}archive/").status_code == 204
        assert api_key_client.post(f"{one}archive/").status_code == 200
        assert api_key_client.delete(one).status_code == 204
        assert api_key_client.get(one).status_code == 404

    def test_scopes_do_not_mix(self, api_key_client, urls):
        proj_page = create(api_key_client, urls["proj"])
        ws_page = create(api_key_client, urls["ws"])
        assert api_key_client.get(f"{urls['ws']}{proj_page['id']}/").status_code == 404
        assert [p["id"] for p in api_key_client.get(urls["ws"]).json()["results"]] == [ws_page["id"]]

    def test_nesting_and_archive_cascade(self, api_key_client, urls):
        parent = create(api_key_client, urls["proj"])
        child = create(api_key_client, urls["proj"], name="Child", parent_id=parent["id"])
        assert child["parent_id"] == parent["id"]
        only = api_key_client.get(urls["proj"], {"parent_id": parent["id"]}).json()["results"]
        assert [p["id"] for p in only] == [child["id"]]
        api_key_client.post(f"{urls['proj']}{parent['id']}/archive/")
        assert Page.objects.get(pk=child["id"]).archived_at is not None
        res = api_key_client.post(
            urls["proj"], {"name": "x", "description_html": "<p></p>", "parent_id": parent["id"]}, format="json"
        )
        assert res.status_code == 400 and "parent_id" in res.json()

    def test_locked_page_refuses_edits_but_can_be_unlocked(self, api_key_client, urls):
        page = create(api_key_client, urls["proj"], is_locked=True)
        one = f"{urls['proj']}{page['id']}/"
        assert api_key_client.put(one, {"description_html": "<p>x</p>"}, format="json").status_code == 400
        assert api_key_client.put(one, {"is_locked": False}, format="json").status_code == 200
        assert api_key_client.put(one, {"description_html": "<p>x</p>"}, format="json").status_code == 200

    @pytest.mark.parametrize(
        "body, key",
        [
            ({"name": ""}, "name"),
            ({"name": "x", "access": 3}, "access"),
            ({"name": "x", "collection_id": "8c1b1b1e-0000-4000-8000-000000000000"}, "collection_id"),
            ({"name": "x", "parent_id": "nope"}, "parent_id"),
        ],
    )
    def test_validation(self, api_key_client, urls, body, key):
        res = api_key_client.post(urls["proj"], body, format="json")
        assert res.status_code == 400 and key in res.json()

    def test_live_down_writes_nothing(self, api_key_client, urls, monkeypatch):
        def down(*a):
            raise LiveUnavailable("refused")

        monkeypatch.setattr("plane.oces.page_views.render", down)
        res = api_key_client.post(urls["proj"], {"name": "x", "description_html": "<p>a</p>"}, format="json")
        assert res.status_code == 502 and not Page.objects.filter(name="x").exists()

    def test_permissions(self, api_client, api_key_client, urls, workspace, project, create_user):
        private = create(api_key_client, urls["proj"], access=1)
        public = create(api_key_client, urls["proj"], name="Public")
        ws_page = create(api_key_client, urls["ws"])

        other = member(workspace, project, "m@example.com")
        api_client.force_authenticate(user=other)
        ids = [p["id"] for p in api_client.get(urls["proj"]).json()["results"]]
        assert ids == [public["id"]]
        assert api_client.get(f"{urls['proj']}{private['id']}/").status_code in (403, 404)
        # members edit public pages but cannot archive or delete someone else's
        assert api_client.put(f"{urls['proj']}{public['id']}/", {"name": "Edited"}, format="json").status_code == 200
        assert api_client.put(f"{urls['proj']}{public['id']}/", {"access": 1}, format="json").status_code == 400
        assert api_client.post(f"{urls['proj']}{public['id']}/archive/").status_code == 403
        assert api_client.get(f"{urls['ws']}{ws_page['id']}/").status_code == 200

        guest = member(workspace, project, "g@example.com", ws_role=5, project_role=5)
        api_client.force_authenticate(user=guest)
        assert api_client.get(urls["proj"]).json()["results"] == []
        assert (
            api_client.post(urls["proj"], {"name": "g", "description_html": "<p></p>"}, format="json").status_code
            == 403
        )
        assert api_client.get(urls["ws"]).status_code == 403

        outsider = member(workspace, project, "o@example.com", project_role=None)
        api_client.force_authenticate(user=outsider)
        assert api_client.get(urls["proj"]).status_code == 403

    def test_work_item_links(self, api_client, api_key_client, urls, workspace, project, create_user):
        page = create(api_key_client, urls["proj"])
        private = create(api_key_client, urls["ws"], access=1)
        issue = Issue.objects.create(name="i", project=project, workspace=workspace, created_by=create_user)
        links = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/pages/"

        res = api_key_client.post(links, {"page_id": page["id"]}, format="json")
        assert res.status_code == 201 and res.json()["page"]["name"] == "Runbook"
        link_id = res.json()["id"]
        assert api_key_client.post(links, {"page_id": page["id"]}, format="json").status_code == 200
        api_key_client.post(links, {"page_id": private["id"]}, format="json")
        assert api_key_client.get(links).json()["total_results"] == 2

        # another member does not see the private page's link, and cannot link it
        other = member(workspace, project, "m2@example.com")
        api_client.force_authenticate(user=other)
        assert [x["id"] for x in api_client.get(links).json()["results"]] == [link_id]
        assert api_client.post(links, {"page_id": private["id"]}, format="json").status_code == 400

        assert api_key_client.delete(f"{links}{link_id}/").status_code == 204
        assert api_key_client.get(f"{links}{link_id}/").status_code == 404


def test_render_calls_live_with_the_shared_secret(monkeypatch, settings):
    """The real client: posts to the live server and decodes the binary it returns."""
    seen = {}

    class Res:
        status_code = 200

        def json(self):
            return {
                "description_binary": base64.b64encode(b"\x01\x02").decode(),
                "description_html": "<p>a</p>",
                "description_json": {},
            }

    def post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers)
        return Res()

    monkeypatch.setenv("OCES_LIVE_INTERNAL_URL", "http://live:3000/live")
    monkeypatch.setenv("LIVE_SERVER_SECRET_KEY", "s3")
    monkeypatch.setattr(page_content.requests, "post", post)
    out = page_content.render("p1", "Name", "<p>a</p>")
    assert out["description_binary"] == b"\x01\x02"
    assert seen["url"] == "http://live:3000/live/oces/page-content/"
    assert seen["headers"]["live-server-secret-key"] == "s3"
