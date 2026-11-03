# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
import requests

from plane.db.models import User, WorkspaceMember
from plane.oces import version
from plane.oces.models import VersionStatus

KEYS = {
    "current",
    "latest",
    "update_available",
    "upstream_current",
    "upstream_latest",
    "upstream_update_available",
    "checked_at",
}


@pytest.fixture
def github(monkeypatch):
    calls = []
    answers = {
        "0ces/plan/tags?per_page=100": [{"name": "oces-v1.4.3-9"}, {"name": "oces-v1.4.3-10"}, {"name": "v1.4.3"}],
        "makeplane/plane/releases/latest": {"tag_name": "v1.5.0"},
    }

    def fake(path):
        calls.append(path)
        answer = answers[path]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(version, "_github", fake)
    monkeypatch.setenv("OCES_VERSION", "oces-v1.4.3-3")
    monkeypatch.setattr("plane.oces.tasks.check_versions.delay", lambda: None)
    return answers, calls


@pytest.mark.django_db
class TestVersionCheck:
    def test_compares_tags_by_number(self, github):
        version.refresh()
        out = version.info()
        assert KEYS <= set(out)
        assert out["latest"] == "oces-v1.4.3-10" and out["update_available"] is True
        assert out["upstream_current"] == "v1.4.3" and out["upstream_latest"] == "v1.5.0"
        assert out["upstream_update_available"] is True
        assert out["latest_url"].endswith("/releases/tag/oces-v1.4.3-10")

    def test_up_to_date(self, github, monkeypatch):
        answers, _ = github
        answers["makeplane/plane/releases/latest"] = {"tag_name": "v1.4.3"}
        monkeypatch.setenv("OCES_VERSION", "oces-v1.4.3-10")
        version.refresh()
        out = version.info()
        assert out["update_available"] is False and out["upstream_update_available"] is False

    def test_failure_keeps_the_last_answer(self, github):
        answers, _ = github
        version.refresh()
        answers["makeplane/plane/releases/latest"] = requests.ConnectionError("offline")
        version.refresh()
        assert VersionStatus.objects.get().upstream_latest == "v1.5.0"

    def test_can_be_turned_off(self, github, monkeypatch):
        _, calls = github
        monkeypatch.setenv("OCES_VERSION_CHECK", "0")
        version.refresh()
        out = version.info()
        assert calls == [] and out["check_enabled"] is False and out["latest"] is None

    def test_dev_build_never_claims_an_update(self, github, monkeypatch):
        monkeypatch.delenv("OCES_VERSION")
        version.refresh()
        out = version.info()
        assert out["current"] == "dev" and out["update_available"] is False


@pytest.mark.contract
def test_endpoints(api_key_client, api_client, github, workspace):
    version.refresh()
    assert KEYS <= set(api_key_client.get("/api/v1/oces/version/").json())
    assert api_client.get("/api/oces/version/").status_code in (401, 403)

    member = User.objects.create(email="m@example.com", username="m")
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    api_client.force_authenticate(user=member)
    assert api_client.get("/api/oces/version/").status_code == 403
    api_client.force_authenticate(user=workspace.owner)
    assert api_client.get("/api/oces/version/").json()["update_available"] is True
