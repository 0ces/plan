# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PublicAPIView
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.app.permissions import ProjectAdminPermission, ProjectLitePermission
from plane.db.models import Issue, IssueType, Project
from plane.db.models.issue_type import ProjectIssueType

from .serializers import WorkItemTypeSerializer
from .work_item_types import project_types

DUPLICATE_NAME = "A work item type with this name already exists in the project."
EDITABLE = {"name", "description", "logo_props", "is_active", "level", "external_source", "external_id"}


def _error(message, code=None, http=status.HTTP_400_BAD_REQUEST, **extra):
    body = {"error": message, **extra}
    if code:
        body["code"] = code
    return Response(body, status=http)


class WorkItemTypeMixin:
    """Project-scoped work item types. Reads for project members, writes for project admins."""

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [ProjectLitePermission()]
        return [ProjectAdminPermission()]

    def _project(self, slug, project_id):
        return get_object_or_404(Project, pk=project_id, workspace__slug=slug)

    def _out(self, obj, project_id, many=False):
        return WorkItemTypeSerializer(obj, many=many, context={"project_id": project_id}).data

    def _name_taken(self, project_id, name, exclude_id=None):
        qs = project_types(project_id).filter(name__iexact=name)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        return qs.exists()

    def _payload(self):
        if not isinstance(self.request.data, dict):
            return None, _error("Send a JSON object.")
        return {k: v for k, v in self.request.data.items() if k in EDITABLE}, None


class WorkItemTypeListCreateMixin(WorkItemTypeMixin):
    def get(self, request, slug, project_id):
        self._project(slug, project_id)
        # Plain array, as the official API (the SDK does not expect pagination here).
        return Response(self._out(project_types(project_id), project_id, many=True))

    def post(self, request, slug, project_id):
        project = self._project(slug, project_id)
        if not project.is_issue_type_enabled:
            return _error(
                "Work item types are off for this project. Turn on the work_item_types feature first.",
                code="work_item_types_disabled",
            )
        data, err = self._payload()
        if err:
            return err
        serializer = WorkItemTypeSerializer(data=data, context={"project_id": project_id})
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        if self._name_taken(project_id, name):
            return _error(
                "A work item type with this name already exists in the project.", http=status.HTTP_409_CONFLICT
            )
        is_epic = request.data.get("is_epic") is True
        if is_epic and project_types(project_id).filter(is_epic=True).exists():
            return _error("This project already has an epic type.")
        with transaction.atomic():
            issue_type = serializer.save(workspace_id=project.workspace_id, is_epic=is_epic, is_default=False)
            ProjectIssueType.objects.create(project=project, issue_type=issue_type, level=int(issue_type.level))
        return Response(self._out(issue_type, project_id), status=status.HTTP_201_CREATED)


class WorkItemTypeDetailMixin(WorkItemTypeMixin):
    def _get(self, slug, project_id, type_id):
        self._project(slug, project_id)
        return get_object_or_404(project_types(project_id), pk=type_id)

    def get(self, request, slug, project_id, type_id):
        return Response(self._out(self._get(slug, project_id, type_id), project_id))

    def patch(self, request, slug, project_id, type_id):
        issue_type = self._get(slug, project_id, type_id)
        link = ProjectIssueType.objects.get(project_id=project_id, issue_type=issue_type)
        data, err = self._payload()
        if err:
            return err
        if "is_epic" in request.data and request.data["is_epic"] != issue_type.is_epic:
            return _error("is_epic cannot be changed after a type is created.")
        make_default = request.data.get("is_default")
        if make_default is False and link.is_default:
            return _error("A project needs a default type. Make another type the default instead.")
        if make_default is True and issue_type.is_epic:
            return _error("The epic type cannot be the default.")
        if data.get("is_active") is False and (link.is_default or make_default is True):
            return _error("The default type cannot be deactivated.")
        serializer = WorkItemTypeSerializer(issue_type, data=data, partial=True, context={"project_id": project_id})
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data.get("name")
        if name and self._name_taken(project_id, name, exclude_id=issue_type.id):
            return _error(
                "A work item type with this name already exists in the project.", http=status.HTTP_409_CONFLICT
            )
        with transaction.atomic():
            issue_type = serializer.save()
            if make_default is True and not link.is_default:
                others = ProjectIssueType.objects.filter(project_id=project_id).exclude(pk=link.pk)
                IssueType.objects.filter(project_issue_types__in=others).update(is_default=False)
                others.update(is_default=False)
                link.is_default = True
                issue_type.is_default = True
                issue_type.save()
            if "level" in data:
                link.level = int(issue_type.level)
            link.save()
        return Response(self._out(issue_type, project_id))

    def delete(self, request, slug, project_id, type_id):
        issue_type = self._get(slug, project_id, type_id)
        link = ProjectIssueType.objects.get(project_id=project_id, issue_type=issue_type)
        if link.is_default:
            return _error("The default type cannot be deleted.")
        in_use = Issue.all_objects.filter(project_id=project_id, type=issue_type).count()
        if in_use:
            return _error("Work items still use this type. Change their type first.", in_use=in_use)
        with transaction.atomic():
            link.delete(soft=False)
            if not ProjectIssueType.objects.filter(issue_type=issue_type).exists():
                issue_type.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


# Public API (X-Api-Key)
class WorkItemTypeListCreateAPIEndpoint(WorkItemTypeListCreateMixin, PublicAPIView):
    pass


class WorkItemTypeDetailAPIEndpoint(WorkItemTypeDetailMixin, PublicAPIView):
    pass


# Internal API (session) for the web app
class WorkItemTypeListCreateEndpoint(WorkItemTypeListCreateMixin, AppAPIView):
    pass


class WorkItemTypeDetailEndpoint(WorkItemTypeDetailMixin, AppAPIView):
    pass
