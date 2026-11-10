# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json

import pytest
from rest_framework.test import APIClient

from plane.db.models import Issue
from plane.oces.bitbucket import KEY, signature_ok

from .test_work_item_types import make_project
from .test_worklogs import person


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "DEMO")


@pytest.fixture
def items(project, create_user):
    make = lambda n: Issue.objects.create(  # noqa: E731
        name=n, project=project, workspace=project.workspace, created_by=create_user
    )
    return make("Login"), make("Checkout")


def payload(number=12, title="DEMO-1 fix login", branch="feature/demo-2-checkout", state="OPEN", description=""):
    return {
        "repository": {"full_name": "acme/web"},
        "pullrequest": {
            "id": number,
            "title": title,
            "description": description,
            "state": state,
            "author": {"display_name": "Ana"},
            "source": {"branch": {"name": branch}},
            "destination": {"branch": {"name": "main"}},
            "links": {"html": {"href": f"https://bitbucket.org/acme/web/pull-requests/{number}"}},
            "updated_on": "2026-11-10T12:00:00.000000+00:00",
        },
    }


def deliver(project, secret, body, event="pullrequest:created", signature=None):
    raw = json.dumps(body).encode()
    sig = signature if signature is not None else "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return APIClient().post(
        f"/api/oces/bitbucket/{project.workspace.slug}/webhook/",
        raw,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE=sig,
        HTTP_X_EVENT_KEY=event,
    )


def prs(client, project, item):
    base = f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/oces"
    return client.get(f"{base}/work-items/{item.id}/pull-requests/").json()


def test_signature_matches_bitbucket_docs_example():
    sig = "sha256=a4771c39fbe90f317c7824e83ddef3caae9cb3d976c214ace1f2937e133263c9"
    assert signature_ok("It's a Secret to Everybody", b"Hello World!", sig)
    assert not signature_ok("other", b"Hello World!", sig)


def test_key_pattern():
    found = {(m.group(1).upper(), m.group(2)) for m in KEY.finditer("feature/demo-7-login DEMO-12, DEMO-45a 2DEMO-9")}
    assert found == {("DEMO", "7"), ("DEMO", "12")}


@pytest.mark.contract
class TestBitbucket:
    def test_setup_and_links(self, session_client, api_key_client, project, items):
        login, checkout = items
        url = f"/api/workspaces/{project.workspace.slug}/oces/bitbucket/"
        assert session_client.get(url).json() == {"enabled": False}
        conf = session_client.post(url).json()
        assert conf["enabled"] and conf["webhook_url"].endswith(
            f"/api/oces/bitbucket/{project.workspace.slug}/webhook/"
        )
        secret = conf["secret"]

        res = deliver(project, secret, payload())
        assert res.status_code == 200, res.content
        assert res.json()["work_items"] == 2
        got = prs(session_client, project, login)
        assert got[0]["number"] == 12 and got[0]["state"] == "OPEN" and got[0]["repository"] == "acme/web"
        assert prs(session_client, project, checkout)[0]["source_branch"] == "feature/demo-2-checkout"

        # merged, and the branch link dropped: only DEMO-1 stays linked
        deliver(project, secret, payload(branch="fix", state="MERGED"), event="pullrequest:fulfilled")
        assert prs(session_client, project, login)[0]["state"] == "MERGED"
        assert prs(session_client, project, checkout) == []

        public = (
            f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/work-items/{login.id}/pull-requests/"
        )
        assert api_key_client.get(public).json()[0]["number"] == 12
        assert session_client.get(url).json()["pull_requests"] == 1

    def test_rejects_bad_deliveries(self, session_client, project, items):
        assert deliver(project, "x", payload()).status_code == 404  # not set up
        url = f"/api/workspaces/{project.workspace.slug}/oces/bitbucket/"
        secret = session_client.post(url).json()["secret"]
        assert deliver(project, "wrong", payload()).status_code == 401
        assert deliver(project, secret, payload(), signature="").status_code == 401
        assert deliver(project, secret, {"pullrequest": {}}).status_code == 400
        assert deliver(project, secret, {}, event="repo:push").json()["ignored"] == "repo:push"

        # a new secret replaces the old one; turning off stops deliveries
        new = session_client.post(url).json()["secret"]
        assert deliver(project, secret, payload()).status_code == 401
        assert deliver(project, new, payload()).status_code == 200
        assert session_client.delete(url).status_code == 204
        assert deliver(project, new, payload()).status_code == 404

    def test_link_only_to_bitbucket(self, session_client, project, items):
        secret = session_client.post(f"/api/workspaces/{project.workspace.slug}/oces/bitbucket/").json()["secret"]
        body = payload()
        body["pullrequest"]["links"]["html"]["href"] = "javascript:alert(1)"
        deliver(project, secret, body)
        assert prs(session_client, project, items[0])[0]["url"] == "https://bitbucket.org/acme/web/pull-requests/12"

    def test_settings_admins_only(self, project):
        _, member = person(project, "dev2@oces.test", 15)
        assert member.get(f"/api/workspaces/{project.workspace.slug}/oces/bitbucket/").status_code == 403
