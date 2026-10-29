# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PublicAPIView
from plane.app.permissions import (
    ProjectAdminPermission,
    ProjectLitePermission,
    WorkspaceOwnerPermission,
    WorkspaceUserPermission,
)
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Project, Workspace

from .features import (
    BUILT_PROJECT_KEYS,
    BUILT_WORKSPACE_KEYS,
    PROJECT_KEYS,
    WORKSPACE_KEYS,
    validate_changes,
)
from .models import ProjectFeature, WorkspaceFeature
from .work_item_types import enable_project_types


class WorkspaceFeaturesMixin:
    """GET for any workspace member, PATCH for workspace admins."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [WorkspaceOwnerPermission()]
        return [WorkspaceUserPermission()]

    @staticmethod
    def _read(row):
        return {key: bool(attr and row and getattr(row, attr)) for key, attr in WORKSPACE_KEYS.items()}

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        return Response(self._read(WorkspaceFeature.objects.filter(workspace=workspace).first()))

    def patch(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        changes, error = validate_changes(request.data, WORKSPACE_KEYS, BUILT_WORKSPACE_KEYS)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)
        row, _ = WorkspaceFeature.objects.get_or_create(workspace=workspace)
        for key, value in changes.items():
            setattr(row, WORKSPACE_KEYS[key], value)
        row.save()
        return Response(self._read(row))


class ProjectFeaturesMixin:
    """GET for any project member, PATCH for project admins."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [ProjectAdminPermission()]
        return [ProjectLitePermission()]

    @staticmethod
    def _read(project, row):
        result = {}
        for key, spec in PROJECT_KEYS.items():
            if spec is None:
                result[key] = False
                continue
            where, attr = spec
            target = project if where == "project" else row
            result[key] = bool(target and getattr(target, attr))
        return result

    def get(self, request, slug, project_id):
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        return Response(self._read(project, ProjectFeature.objects.filter(project=project).first()))

    def patch(self, request, slug, project_id):
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        changes, error = validate_changes(request.data, PROJECT_KEYS, BUILT_PROJECT_KEYS)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)
        row = ProjectFeature.objects.filter(project=project).first()
        touched = set()
        for key, value in changes.items():
            where, attr = PROJECT_KEYS[key]
            if where == "oces" and row is None:
                row = ProjectFeature.objects.create(project=project)
            setattr(project if where == "project" else row, attr, value)
            touched.add(where)
        if "project" in touched:
            project.save()
        if changes.get("work_item_types"):
            enable_project_types(project)  # creates default types once, types untyped items
        if "oces" in touched:
            row.save()
        return Response(self._read(project, row))


# Public API (X-Api-Key), paths match the official /api/v1/ contract.
class WorkspaceFeaturesAPIEndpoint(WorkspaceFeaturesMixin, PublicAPIView):
    pass


class ProjectFeaturesAPIEndpoint(ProjectFeaturesMixin, PublicAPIView):
    pass


# Internal API (session) for the web app settings screens.
class WorkspaceFeaturesEndpoint(WorkspaceFeaturesMixin, AppAPIView):
    pass


class ProjectFeaturesEndpoint(ProjectFeaturesMixin, AppAPIView):
    pass
