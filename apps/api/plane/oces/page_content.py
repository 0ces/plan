# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""HTML -> editor document for pages, done by the live server (apps/live/src/oces/page-content.ts).

The web editor loads description_binary (Yjs), not description_html, so every HTML write
through the API is converted with the editor's own code. The live server also swaps the
content of a page that is open right now, so editors do not save the old text over it.
"""

import base64
import os

import requests
from django.conf import settings


class LiveUnavailable(Exception):
    pass


def live_url():
    # The API container reaches live over the compose network; LIVE_BASE_URL is usually unset.
    base = os.environ.get("OCES_LIVE_INTERNAL_URL") or settings.LIVE_URL or "http://live:3000/live/"
    return base.rstrip("/") + "/oces/page-content/"


def render(page_id, name, html):
    """Return the fields to store: description_binary (bytes), description_html, description_json."""
    secret = os.environ.get("LIVE_SERVER_SECRET_KEY", "")
    try:
        res = requests.post(
            live_url(),
            json={"page_id": str(page_id), "name": name, "description_html": html},
            headers={"live-server-secret-key": secret},
            timeout=15,
        )
    except requests.RequestException as e:
        raise LiveUnavailable(str(e)) from e
    if res.status_code != 200:
        raise LiveUnavailable(f"live answered {res.status_code}")
    body = res.json()
    return {
        "description_binary": base64.b64decode(body["description_binary"]),
        "description_html": body["description_html"],
        "description_json": body["description_json"],
    }
