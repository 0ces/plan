# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Version endpoints: API key (monitoring) and session (banners for admins)."""

from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PublicAPIView
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import WorkspaceMember
from plane.license.models import InstanceAdmin

from .version import info


class VersionAPIEndpoint(PublicAPIView):
    """GET /api/v1/oces/version/ with any API key."""

    def get(self, request):
        return Response(info())


class AnyAdmin(BasePermission):
    """Instance admins and workspace admins see update notices; members do not."""

    def has_permission(self, request, view):
        user = request.user
        if user.is_anonymous:
            return False
        return (
            InstanceAdmin.objects.filter(user=user).exists()
            or WorkspaceMember.objects.filter(member=user, role=20, is_active=True).exists()
        )


class VersionEndpoint(AppAPIView):
    """GET /api/oces/version/ for the web and admin apps."""

    def get_permissions(self):
        return [AnyAdmin()]

    def get(self, request):
        return Response(info())
