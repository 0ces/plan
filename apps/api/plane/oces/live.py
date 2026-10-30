# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Live updates: tell open browsers that something changed, so they reload it.

Events carry ids only, never data; the browser re-fetches through the normal API,
which applies the usual permissions. Published to Redis channel `oces:live:<slug>`;
the live server (apps/live/src/oces) forwards them over a websocket.

Two sources:
- LiveEventsMiddleware: every successful write request (web app, public API, MCP).
  Catches bulk_create/bulk_update writes that model signals would miss.
- issue_activity task finishing: the activity feed is written in the background,
  after the request already answered.
"""

import json
import logging
import re

from celery.signals import task_postrun
from rest_framework.response import Response

from plane.app.permissions import WorkspaceUserPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Project, ProjectMember
from plane.settings.redis import redis_instance

logger = logging.getLogger("plane.oces.live")

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Per-user settings and bookkeeping; nothing other viewers need to reload.
SKIP_PATH = re.compile(
    r"/(user-properties|user-favorites|favorites|recent-visits|notifications|users/me|"
    r"user-activity|mark-read|sign-|unread|onboard|tour|oces/live-access)(/|$)"
)
SKIP_ROUTE = re.compile(r"(^|-)user-|favorite")
ISSUE_IN_PATH = re.compile(r"/(issues|work-items|work_items|epics|intake-issues)/(?P<id>[0-9a-f-]{36})/")
# A create's id is only in the response: POST .../issues/ or .../work-items/
ISSUE_LIST_PATH = re.compile(r"/(issues|work-items|epics)/$")
ACTIVITY_TASK = "plane.bgtasks.issue_activities_task.issue_activity"


def channel(slug):
    return f"oces:live:{slug}"


def publish(slug, event):
    if not slug:
        return
    try:
        redis_instance().publish(channel(slug), json.dumps(event, default=str))
    except Exception:  # live updates are best effort; never break the write
        logger.warning("live publish failed", exc_info=True)


def event_from_request(request, response):
    """Build the event for a write request, or None when nothing should be sent."""
    if request.method not in WRITE_METHODS or response.status_code >= 400:
        return None
    match = getattr(request, "resolver_match", None)
    if not match or "slug" not in match.kwargs or SKIP_PATH.search(request.path):
        return None
    if SKIP_ROUTE.search(match.url_name or ""):
        return None
    kwargs = match.kwargs
    issue_id = kwargs.get("issue_id") or kwargs.get("work_item_id")
    if not issue_id:
        found = ISSUE_IN_PATH.search(request.path)
        issue_id = found and found.group("id")
    if not issue_id and request.method == "POST" and ISSUE_LIST_PATH.search(request.path):
        data = getattr(response, "data", None)
        issue_id = data.get("id") if isinstance(data, dict) else None
    return {
        "slug": kwargs["slug"],
        "project_id": kwargs.get("project_id"),
        "issue_id": issue_id or None,
        "cycle_id": kwargs.get("cycle_id"),
        "module_id": kwargs.get("module_id"),
        "route": match.url_name,
        "action": request.method.lower(),
    }


class LiveEventsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        event = event_from_request(request, response)
        if event:
            publish(event.pop("slug"), event)
        return response


@task_postrun.connect
def activity_written(sender=None, kwargs=None, **_):
    if getattr(sender, "name", None) != ACTIVITY_TASK or not kwargs:
        return
    slug = Project.objects.filter(id=kwargs.get("project_id")).values_list("workspace__slug", flat=True).first()
    publish(
        slug,
        {
            "project_id": kwargs.get("project_id"),
            "issue_id": kwargs.get("issue_id"),
            "action": "activity",
        },
    )


class LiveAccessEndpoint(BaseAPIView):
    """Which projects' events this session may receive. Called by the live server with the
    browser's cookie on connect and again when project membership changes."""

    permission_classes = [WorkspaceUserPermission]

    def get(self, request, slug):
        project_ids = ProjectMember.objects.filter(
            workspace__slug=slug, member=request.user, is_active=True, project__archived_at__isnull=True
        ).values_list("project_id", flat=True)
        return Response({"user_id": str(request.user.id), "project_ids": [str(p) for p in project_ids]})
