# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which fork release is running, and whether a newer fork release or Plane release exists.

The image carries its tag and commit (OCES_VERSION / OCES_COMMIT, set at build time).
A beat task (tasks.check_versions) asks GitHub's public API every 6 hours and keeps the
answer in VersionStatus. OCES_VERSION_CHECK=0 turns the check off for offline installs;
OCES_GITHUB_TOKEN (read-only) lets it see the fork's tags while the repo is private.
"""

import logging
import os
import re
from datetime import timedelta

import requests
from django.utils import timezone

from .models import VersionStatus

log = logging.getLogger("plane.oces")

FORK_REPO = "0ces/plan"
UPSTREAM_REPO = "makeplane/plane"
# shortcut: only used when the running version is not a release tag (dev builds);
# keep in step with docs/fork/UPSTREAM_BASE
UPSTREAM_BASE = "v1.4.3"
TAG = re.compile(r"^oces-v(\d+)\.(\d+)\.(\d+)-(\d+)$")
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
STALE = timedelta(hours=7)


def _key(pattern, value):
    m = pattern.match(value or "")
    return tuple(int(x) for x in m.groups()) if m else None


def current():
    return os.environ.get("OCES_VERSION") or "dev"


def upstream_current():
    k = _key(TAG, current())
    return "v%d.%d.%d" % k[:3] if k else UPSTREAM_BASE


def check_enabled():
    return os.environ.get("OCES_VERSION_CHECK", "1").strip().lower() not in ("0", "false", "off", "no")


def _github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "oces-plane-version-check"}
    # only needed while the fork repo is private; a read-only token is enough
    if os.environ.get("OCES_GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['OCES_GITHUB_TOKEN']}"
    res = requests.get(f"https://api.github.com/repos/{path}", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def latest_fork_tag():
    # shortcut: reads the first 100 tags only, plenty for years of oces-v* releases
    names = [t["name"] for t in _github(f"{FORK_REPO}/tags?per_page=100") if _key(TAG, t.get("name"))]
    return max(names, key=lambda n: _key(TAG, n)) if names else None


def latest_upstream():
    return _github(f"{UPSTREAM_REPO}/releases/latest")["tag_name"]


def refresh():
    """Ask GitHub; keep the previous answer for any part that fails (offline, rate limited)."""
    if not check_enabled():
        return
    status = VersionStatus.objects.first() or VersionStatus()
    for field, fetch in (("fork_latest", latest_fork_tag), ("upstream_latest", latest_upstream)):
        try:
            setattr(status, field, fetch() or getattr(status, field))
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            log.info("oces version check: %s failed: %s", field, e)
    status.checked_at = timezone.now()
    status.save()


def info():
    """The stable shape served by /api/v1/oces/version/ (Uptime Kuma polls it)."""
    status = VersionStatus.objects.first()
    if check_enabled() and (status is None or not status.checked_at or timezone.now() - status.checked_at > STALE):
        from .tasks import check_versions

        check_versions.delay()
    cur, up_cur = current(), upstream_current()
    latest = status.fork_latest if status else None
    up_latest = status.upstream_latest if status else None
    cur_key, latest_key = _key(TAG, cur), _key(TAG, latest)
    up_cur_key, up_latest_key = _key(SEMVER, up_cur), _key(SEMVER, up_latest)
    return {
        "current": cur,
        "commit": os.environ.get("OCES_COMMIT") or None,
        "latest": latest,
        "update_available": bool(cur_key and latest_key and latest_key > cur_key),
        "latest_url": f"https://github.com/{FORK_REPO}/releases/tag/{latest}" if latest else None,
        "upstream_current": up_cur,
        "upstream_latest": up_latest,
        "upstream_update_available": bool(up_cur_key and up_latest_key and up_latest_key > up_cur_key),
        "upstream_latest_url": f"https://github.com/{UPSTREAM_REPO}/releases/tag/{up_latest}" if up_latest else None,
        "checked_at": status.checked_at if status else None,
        "check_enabled": check_enabled(),
    }
