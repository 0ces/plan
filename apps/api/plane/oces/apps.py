# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.apps import AppConfig


class OcesConfig(AppConfig):
    """Our own features on top of Plane CE. Kept in one app so upstream merges stay clean."""

    name = "plane.oces"
    label = "oces"
    default_auto_field = "django.db.models.BigAutoField"
