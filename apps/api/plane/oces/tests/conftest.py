# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Reuse upstream's fixtures (users, workspace, API key and session clients).
from plane.tests.conftest import *  # noqa: F401,F403

import pytest  # noqa: E402

from plane.celery import app as celery_app  # noqa: E402


@pytest.fixture(autouse=True)
def celery_in_process(settings):
    """No broker in tests: run background tasks (activity, notifications) inline."""
    settings.WEB_URL = settings.WEB_URL or "http://localhost"
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture(autouse=True)
def no_api_rate_limit(monkeypatch):
    """The API key throttle counts in Redis across tests; contract tests make many calls."""
    from plane.api.rate_limit import ApiKeyRateThrottle

    monkeypatch.setattr(ApiKeyRateThrottle, "allow_request", lambda self, request, view: True)
