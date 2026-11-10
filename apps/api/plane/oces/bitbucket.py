# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Bitbucket Cloud pull requests on work items.

A workspace admin turns it on (Workspace settings → Bitbucket) and gets a webhook URL and a secret to
paste into a Bitbucket workspace or repository webhook with the pull request events. Every delivery is
checked against the secret (X-Hub-Signature: sha256=<hmac of the raw body>). A pull request is linked
to each work item whose id (DEMO-7) appears in its title, source branch or description.

POST /api/oces/bitbucket/{slug}/webhook/                         Bitbucket → Plane (no login, signed)
GET|POST|DELETE workspaces/{slug}/oces/bitbucket/                settings (workspace admins)
GET projects/{p}/oces/work-items/{w}/pull-requests/              a work item's pull requests (members)
GET /api/v1/.../projects/{p}/work-items/{w}/pull-requests/       same, public API
"""

import hashlib
import hmac
import json
import re
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response

from rest_framework.permissions import BasePermission

from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Issue, Project, Workspace, WorkspaceMember

from .models import BitbucketConnection, PullRequest, WorkItemPullRequest
from .property_views import ProjectScope, _pair

# DEMO-7, demo-7 (branches are often lower case); not inside a longer word or number
KEY = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]{0,11})-(\d{1,9})(?![A-Za-z0-9])")
MAX_KEYS = 50


def mentioned_issues(workspace_id, text):
    pairs = {(m.group(1).upper(), int(m.group(2))) for m in KEY.finditer(text or "")}
    if not pairs:
        return []
    pairs = sorted(pairs)[:MAX_KEYS]
    projects = dict(
        Project.objects.filter(workspace_id=workspace_id, identifier__in={p for p, _ in pairs}).values_list(
            "identifier", "id"
        )
    )
    q = Q()
    for ident, seq in pairs:
        if ident in projects:
            q |= Q(project_id=projects[ident], sequence_id=seq)
    return list(Issue.objects.filter(q, workspace_id=workspace_id)) if q else []


def _get(d, *path):
    for key in path:
        d = d.get(key) if isinstance(d, dict) else None
    return d


def save_pull_request(workspace_id, payload):
    """Create or update the pull request from a webhook payload and relink it. Returns it, or None."""
    pr = _get(payload, "pullrequest") or {}
    repo = str(_get(payload, "repository", "full_name") or "")[:255]
    number = pr.get("id")
    if not repo or not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        return None
    url = str(_get(pr, "links", "html", "href") or "")
    if not url.startswith("https://bitbucket.org/"):  # only ever link back to Bitbucket
        url = f"https://bitbucket.org/{repo}/pull-requests/{number}"
    fields = {
        "title": str(pr.get("title") or "")[:512],
        "url": url[:1024],
        "state": str(pr.get("state") or "OPEN")[:32],
        "author": str(_get(pr, "author", "display_name") or "")[:255],
        "source_branch": str(_get(pr, "source", "branch", "name") or "")[:255],
        "target_branch": str(_get(pr, "destination", "branch", "name") or "")[:255],
        "pr_updated_at": parse_datetime(str(pr.get("updated_on") or "")),
    }
    key = {"workspace_id": workspace_id, "provider": "bitbucket", "repository": repo, "number": number}
    try:
        with transaction.atomic():
            obj, _ = PullRequest.objects.update_or_create(**key, defaults=fields)
    except IntegrityError:  # the same pull request arrived twice at once
        obj = PullRequest.objects.get(**key)
        for k, v in fields.items():
            setattr(obj, k, v)
        obj.save()

    text = " ".join([fields["title"], fields["source_branch"], str(pr.get("description") or "")])
    wanted = {i.id for i in mentioned_issues(workspace_id, text)}
    WorkItemPullRequest.objects.filter(pull_request=obj).exclude(issue_id__in=wanted).delete()
    have = set(WorkItemPullRequest.objects.filter(pull_request=obj).values_list("issue_id", flat=True))
    WorkItemPullRequest.objects.bulk_create(
        [WorkItemPullRequest(pull_request=obj, issue_id=i) for i in wanted - have], ignore_conflicts=True
    )
    return obj


def signature_ok(secret, body, header):
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


@method_decorator(csrf_exempt, name="dispatch")
class BitbucketWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, slug):
        conn = BitbucketConnection.objects.filter(workspace__slug=slug, is_active=True).first()
        if conn is None:
            return JsonResponse({"error": "Bitbucket is not set up for this workspace."}, status=404)
        if not signature_ok(conn.secret, request.body, request.headers.get("X-Hub-Signature")):
            return JsonResponse({"error": "Signature does not match."}, status=401)
        conn.last_event_at = timezone.now()
        conn.save(update_fields=["last_event_at", "updated_at"], disable_auto_set_user=True)
        event = request.headers.get("X-Event-Key", "")
        if not event.startswith("pullrequest:"):
            return JsonResponse({"ok": True, "ignored": event[:64]})
        try:
            payload = json.loads(request.body)
        except ValueError:
            return JsonResponse({"error": "Body is not JSON."}, status=400)
        pr = save_pull_request(conn.workspace_id, payload if isinstance(payload, dict) else {})
        if pr is None:
            return JsonResponse({"error": "No pull request in the payload."}, status=400)
        return JsonResponse({"ok": True, "work_items": pr.links.count()})


def webhook_url(request, slug):
    base = (getattr(settings, "WEB_URL", None) or request.build_absolute_uri("/")).rstrip("/")
    return f"{base}/api/oces/bitbucket/{slug}/webhook/"


class WorkspaceAdminOnly(BasePermission):
    """Admins only (upstream's WorkSpaceAdminPermission also lets members in); the page shows the secret."""

    def has_permission(self, request, view):
        return (
            not request.user.is_anonymous
            and WorkspaceMember.objects.filter(
                workspace__slug=view.kwargs["slug"], member=request.user, role=20, is_active=True
            ).exists()
        )


class BitbucketSettingsEndpoint(AppAPIView):
    permission_classes = [WorkspaceAdminOnly]

    def _out(self, request, slug, conn):
        if conn is None:
            return {"enabled": False}
        return {
            "enabled": True,
            "webhook_url": webhook_url(request, slug),
            "secret": conn.secret,
            "last_event_at": conn.last_event_at.isoformat() if conn.last_event_at else None,
            "pull_requests": PullRequest.objects.filter(workspace_id=conn.workspace_id).count(),
        }

    def get(self, request, slug):
        conn = BitbucketConnection.objects.filter(workspace__slug=slug).first()
        return Response(self._out(request, slug, conn))

    def post(self, request, slug):
        """Turn on, or make a new secret (the old one stops working)."""
        workspace = get_object_or_404(Workspace, slug=slug)
        conn = BitbucketConnection.objects.filter(workspace=workspace).first() or BitbucketConnection(
            workspace=workspace
        )
        conn.secret = secrets.token_urlsafe(32)
        conn.is_active = True
        conn.save()
        return Response(self._out(request, slug, conn))

    def delete(self, request, slug):
        """Turn off. Pull requests already linked stay on their work items."""
        BitbucketConnection.all_objects.filter(workspace__slug=slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def pull_request_out(pr):
    return {
        "id": str(pr.id),
        "provider": pr.provider,
        "repository": pr.repository,
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "state": pr.state,
        "author": pr.author,
        "source_branch": pr.source_branch,
        "target_branch": pr.target_branch,
        "updated_at": pr.pr_updated_at.isoformat() if pr.pr_updated_at else None,
    }


class WorkItemPullRequestsMixin(ProjectScope):
    def get(self, request, slug, project_id, work_item_id):
        item = get_object_or_404(Issue.objects, pk=work_item_id, project_id=project_id, workspace__slug=slug)
        prs = PullRequest.objects.filter(links__issue=item).order_by("-pr_updated_at", "-created_at")
        return Response([pull_request_out(p) for p in prs])


WorkItemPullRequestsAPIEndpoint, WorkItemPullRequestsEndpoint = _pair(WorkItemPullRequestsMixin)
