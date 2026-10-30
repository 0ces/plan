# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item property endpoints at the three scopes of the official API.

Type-scoped:   projects/{p}/work-item-types/{t}/work-item-properties/[{id}/]
Project-flat:  projects/{p}/work-item-properties/[{id}/]
Workspace:     work-item-properties/[{id}/]
Plus options, type links and per-work-item values. Lists are plain arrays.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PublicAPIView
from plane.app.permissions import (
    ProjectAdminPermission,
    ProjectEntityPermission,
    ProjectLitePermission,
    WorkSpaceAdminPermission,
    WorkspaceUserPermission,
)
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Issue, Project, Workspace

from . import properties as P
from .models import WorkItemProperty, WorkItemPropertyValue, WorkItemTypeProperty
from .work_item_types import project_types

READ = ("GET", "HEAD", "OPTIONS")


def option_out(o):
    return {
        "id": str(o.id),
        "name": o.name,
        "description": o.description,
        "sort_order": o.sort_order,
        "logo_props": o.logo_props,
        "is_active": o.is_active,
        "is_default": o.is_default,
        "parent": str(o.parent_id) if o.parent_id else None,
        "property": str(o.property_id),
        "workspace": str(o.workspace_id),
        "project": str(o.project_id) if o.project_id else None,
        "external_source": o.external_source,
        "external_id": o.external_id,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "created_by": str(o.created_by_id) if o.created_by_id else None,
        "updated_by": str(o.updated_by_id) if o.updated_by_id else None,
        "deleted_at": None,
    }


def property_out(p, issue_type_id=None):
    return {
        "id": str(p.id),
        "name": p.name,
        "display_name": p.display_name,
        "description": p.description,
        "logo_props": p.logo_props,
        "sort_order": p.sort_order,
        "property_type": p.property_type,
        "relation_type": p.relation_type,
        "is_required": p.is_required,
        "default_value": p.default_value,
        "settings": p.settings,
        "is_active": p.is_active,
        "is_multi": p.is_multi,
        "validation_rules": p.validation_rules,
        "external_source": p.external_source,
        "external_id": p.external_id,
        "workspace": str(p.workspace_id),
        "project": str(p.project_id) if p.project_id else None,
        "issue_type": str(issue_type_id or p.issue_type_id) if (issue_type_id or p.issue_type_id) else None,
        "issue_type_ids": [str(t) for t in p.type_links.values_list("issue_type_id", flat=True)],
        "options": [option_out(o) for o in p.options.all()],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "created_by": str(p.created_by_id) if p.created_by_id else None,
        "updated_by": str(p.updated_by_id) if p.updated_by_id else None,
        "deleted_at": None,
    }


def many_out(qs, issue_type_id=None):
    return [property_out(p, issue_type_id) for p in qs.prefetch_related("options", "type_links")]


class ProjectScope:
    """Reads for project members, definition writes for project admins."""

    def get_permissions(self):
        return [ProjectLitePermission()] if self.request.method in READ else [ProjectAdminPermission()]

    def project(self, slug, project_id):
        return get_object_or_404(Project, pk=project_id, workspace__slug=slug)

    def issue_type(self, project_id, type_id):
        return get_object_or_404(project_types(project_id), pk=type_id)

    def project_props(self, project):
        return WorkItemProperty.objects.filter(project=project)


class WorkspaceScope:
    def get_permissions(self):
        return [WorkspaceUserPermission()] if self.request.method in READ else [WorkSpaceAdminPermission()]

    def workspace(self, slug):
        return get_object_or_404(Workspace, slug=slug)


# ---------------------------------------------------------------- type-scoped


class TypePropertyListMixin(ProjectScope):
    def get(self, request, slug, project_id, type_id):
        self.project(slug, project_id)
        self.issue_type(project_id, type_id)
        return Response(many_out(P.type_properties(type_id), type_id))

    def post(self, request, slug, project_id, type_id):
        project = self.project(slug, project_id)
        issue_type = self.issue_type(project_id, type_id)
        prop = P.create_property(
            workspace_id=project.workspace_id,
            project_id=project.id,
            issue_type=issue_type,
            data=request.data,
            scope_qs=self.project_props(project),
        )
        return Response(property_out(prop, type_id), status=status.HTTP_201_CREATED)


class TypePropertyDetailMixin(ProjectScope):
    def _get(self, slug, project_id, type_id, property_id):
        self.project(slug, project_id)
        self.issue_type(project_id, type_id)
        return get_object_or_404(P.type_properties(type_id), pk=property_id)

    def get(self, request, slug, project_id, type_id, property_id):
        return Response(property_out(self._get(slug, project_id, type_id, property_id), type_id))

    def patch(self, request, slug, project_id, type_id, property_id):
        prop = self._get(slug, project_id, type_id, property_id)
        scope = WorkItemProperty.objects.filter(project_id=prop.project_id, workspace_id=prop.workspace_id)
        return Response(property_out(P.update_property(prop, request.data, scope), type_id))

    def delete(self, request, slug, project_id, type_id, property_id):
        P.delete_property(self._get(slug, project_id, type_id, property_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TypePropertyLinkMixin(ProjectScope):
    """Attach existing properties to a type, or detach one (the property itself stays)."""

    def post(self, request, slug, project_id, type_id, property_id=None):
        project = self.project(slug, project_id)
        issue_type = self.issue_type(project_id, type_id)
        ids = request.data.get("properties") if isinstance(request.data, dict) else None
        if not isinstance(ids, list) or not ids:
            return Response({"properties": "Send a non-empty list of property ids."}, status=400)
        usable = WorkItemProperty.objects.filter(workspace_id=project.workspace_id).filter(
            Q(project=project) | Q(project__isnull=True)
        )
        try:
            found = list(usable.filter(pk__in=ids))
        except Exception:
            return Response({"properties": "Property ids must be UUIDs."}, status=400)
        if len(found) != len(set(map(str, ids))):
            return Response({"properties": "Some properties do not exist in this project or workspace."}, status=400)
        for prop in found:
            WorkItemTypeProperty.objects.get_or_create(issue_type=issue_type, property=prop)
        return Response({"properties": [str(p.id) for p in found]}, status=status.HTTP_201_CREATED)

    def delete(self, request, slug, project_id, type_id, property_id=None):
        self.project(slug, project_id)
        self.issue_type(project_id, type_id)
        link = get_object_or_404(WorkItemTypeProperty, issue_type_id=type_id, property_id=property_id)
        link.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- project-flat


class ProjectPropertyListMixin(ProjectScope):
    def get(self, request, slug, project_id):
        return Response(many_out(self.project_props(self.project(slug, project_id))))

    def post(self, request, slug, project_id):
        project = self.project(slug, project_id)
        prop = P.create_property(
            workspace_id=project.workspace_id,
            project_id=project.id,
            issue_type=None,
            data=request.data,
            scope_qs=self.project_props(project),
        )
        return Response(property_out(prop), status=status.HTTP_201_CREATED)


class ProjectPropertyDetailMixin(ProjectScope):
    def _get(self, slug, project_id, property_id):
        return get_object_or_404(self.project_props(self.project(slug, project_id)), pk=property_id)

    def get(self, request, slug, project_id, property_id):
        return Response(property_out(self._get(slug, project_id, property_id)))

    def patch(self, request, slug, project_id, property_id):
        prop = self._get(slug, project_id, property_id)
        return Response(property_out(P.update_property(prop, request.data, self.project_props(prop.project))))

    def delete(self, request, slug, project_id, property_id):
        P.delete_property(self._get(slug, project_id, property_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- workspace


class WorkspacePropertyListMixin(WorkspaceScope):
    def get(self, request, slug):
        # Every property the caller can see (workspace-level and their projects'), so the
        # MCP can look a property up by name for a cf[] filter in one call.
        return Response(many_out(P.visible_properties(slug, request.user)))

    def post(self, request, slug):
        workspace = self.workspace(slug)
        prop = P.create_property(
            workspace_id=workspace.id,
            project_id=None,
            issue_type=None,
            data=request.data,
            scope_qs=WorkItemProperty.objects.filter(workspace=workspace, project__isnull=True),
        )
        return Response(property_out(prop), status=status.HTTP_201_CREATED)


class WorkspacePropertyDetailMixin(WorkspaceScope):
    def _get(self, slug, property_id, writable=False):
        qs = WorkItemProperty.objects.filter(workspace__slug=slug, project__isnull=True)
        if not writable:
            qs = P.visible_properties(slug, self.request.user)
        return get_object_or_404(qs, pk=property_id)

    def get(self, request, slug, property_id):
        return Response(property_out(self._get(slug, property_id)))

    def patch(self, request, slug, property_id):
        prop = self._get(slug, property_id, writable=True)
        scope = WorkItemProperty.objects.filter(workspace_id=prop.workspace_id, project__isnull=True)
        return Response(property_out(P.update_property(prop, request.data, scope)))

    def delete(self, request, slug, property_id):
        P.delete_property(self._get(slug, property_id, writable=True))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- options


class OptionsMixin:
    def prop(self, slug, project_id, property_id):
        if project_id:
            project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
            qs = WorkItemProperty.objects.filter(project=project)
        else:
            qs = WorkItemProperty.objects.filter(workspace__slug=slug, project__isnull=True)
        prop = get_object_or_404(qs, pk=property_id)
        if prop.property_type != "OPTION":
            raise ValidationError({"error": "Only OPTION properties have options."})
        return prop

    def get(self, request, slug, property_id, project_id=None, option_id=None):
        prop = self.prop(slug, project_id, property_id)
        if option_id:
            return Response(option_out(get_object_or_404(prop.options, pk=option_id)))
        return Response([option_out(o) for o in prop.options.all()])

    def post(self, request, slug, property_id, project_id=None, option_id=None):
        prop = self.prop(slug, project_id, property_id)
        return Response(option_out(P.save_option(prop, request.data)), status=status.HTTP_201_CREATED)

    def patch(self, request, slug, property_id, project_id=None, option_id=None):
        prop = self.prop(slug, project_id, property_id)
        option = get_object_or_404(prop.options, pk=option_id)
        return Response(option_out(P.save_option(prop, request.data, option)))

    def delete(self, request, slug, property_id, project_id=None, option_id=None):
        prop = self.prop(slug, project_id, property_id)
        option = get_object_or_404(prop.options, pk=option_id)
        option.delete(soft=False)  # removes the values that pointed at it (CASCADE)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectOptionsMixin(OptionsMixin, ProjectScope):
    pass


class WorkspaceOptionsMixin(OptionsMixin, WorkspaceScope):
    pass


# ---------------------------------------------------------------- values


class ValuesMixin:
    """projects/{p}/work-items/{wi}/work-item-properties/{prop}/values/"""

    def get_permissions(self):
        return [ProjectEntityPermission()]

    def _load(self, slug, project_id, work_item_id, property_id):
        issue = get_object_or_404(
            Issue.all_objects.filter(deleted_at__isnull=True).select_related("project"),
            pk=work_item_id,
            project_id=project_id,
            workspace__slug=slug,
        )
        if not P.can_see_issue(self.request.user, issue):
            raise NotFound()
        prop = get_object_or_404(
            WorkItemProperty.objects.filter(workspace_id=issue.workspace_id).filter(
                Q(project_id=project_id) | Q(project__isnull=True)
            ),
            pk=property_id,
        )
        return issue, prop

    def _rows(self, prop, issue):
        rows = list(prop.values.filter(issue=issue).select_related("value_option"))
        for r in rows:
            r.property = prop
        return rows

    def _applies(self, prop, issue):
        links = list(prop.type_links.values_list("issue_type_id", flat=True))
        if links and issue.type_id not in links:
            return Response({"error": "This property is not used by this work item's type."}, status=400)
        if not prop.is_active:
            return Response({"error": "This property is not active."}, status=400)
        return None

    def get(self, request, slug, project_id, work_item_id, property_id):
        issue, prop = self._load(slug, project_id, work_item_id, property_id)
        rows = self._rows(prop, issue)
        if not rows:
            return Response({"error": "No value set for this property."}, status=status.HTTP_404_NOT_FOUND)
        return Response(P.values_response(prop, rows))

    def _write(self, request, slug, project_id, work_item_id, property_id, must_exist):
        issue, prop = self._load(slug, project_id, work_item_id, property_id)
        if err := self._applies(prop, issue):
            return err
        if not isinstance(request.data, dict) or "value" not in request.data:
            return Response({"value": "value is required."}, status=400)
        existed = prop.values.filter(issue=issue).exists()
        if must_exist and not existed:
            return Response({"error": "No value set for this property."}, status=status.HTTP_404_NOT_FOUND)
        external = {k: request.data[k] for k in ("external_id", "external_source") if request.data.get(k)}
        rows = P.set_values(prop, issue, request.data["value"], request.user, external)
        code = status.HTTP_200_OK if existed else status.HTTP_201_CREATED
        return Response(P.values_response(prop, rows), status=code)

    def post(self, request, slug, project_id, work_item_id, property_id):
        return self._write(request, slug, project_id, work_item_id, property_id, must_exist=False)

    def patch(self, request, slug, project_id, work_item_id, property_id):
        return self._write(request, slug, project_id, work_item_id, property_id, must_exist=True)

    def delete(self, request, slug, project_id, work_item_id, property_id):
        issue, prop = self._load(slug, project_id, work_item_id, property_id)
        P.clear_values(prop, issue, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkItemAllValuesMixin(ValuesMixin):
    """Internal: every value of one work item, {property_id: value | [values]}, for the web app."""

    def get(self, request, slug, project_id, work_item_id):
        issue = get_object_or_404(
            Issue.all_objects.filter(deleted_at__isnull=True).select_related("project"),
            pk=work_item_id,
            project_id=project_id,
            workspace__slug=slug,
        )
        if not P.can_see_issue(request.user, issue):
            return Response(status=status.HTTP_404_NOT_FOUND)
        out = {}
        rows = WorkItemPropertyValue.objects.filter(issue=issue).select_related("property", "value_option")
        for r in rows:
            v = P.raw_value(r) if not P.is_rich_text(r.property) else (r.value_text or "")
            key = str(r.property_id)
            if r.property.is_multi:
                out.setdefault(key, []).append(v)
            else:
                out[key] = v
        return Response(out)


# ---------------------------------------------------------------- concrete views


def _pair(mixin):
    public = type(mixin.__name__.replace("Mixin", "APIEndpoint"), (mixin, PublicAPIView), {})
    internal = type(mixin.__name__.replace("Mixin", "Endpoint"), (mixin, AppAPIView), {})
    return public, internal


TypePropertyListAPIEndpoint, TypePropertyListEndpoint = _pair(TypePropertyListMixin)
TypePropertyDetailAPIEndpoint, TypePropertyDetailEndpoint = _pair(TypePropertyDetailMixin)
TypePropertyLinkAPIEndpoint, TypePropertyLinkEndpoint = _pair(TypePropertyLinkMixin)
ProjectPropertyListAPIEndpoint, ProjectPropertyListEndpoint = _pair(ProjectPropertyListMixin)
ProjectPropertyDetailAPIEndpoint, ProjectPropertyDetailEndpoint = _pair(ProjectPropertyDetailMixin)
WorkspacePropertyListAPIEndpoint, WorkspacePropertyListEndpoint = _pair(WorkspacePropertyListMixin)
WorkspacePropertyDetailAPIEndpoint, WorkspacePropertyDetailEndpoint = _pair(WorkspacePropertyDetailMixin)
ProjectOptionsAPIEndpoint, ProjectOptionsEndpoint = _pair(ProjectOptionsMixin)
WorkspaceOptionsAPIEndpoint, WorkspaceOptionsEndpoint = _pair(WorkspaceOptionsMixin)
ValuesAPIEndpoint, ValuesEndpoint = _pair(ValuesMixin)
_, WorkItemAllValuesEndpoint = _pair(WorkItemAllValuesMixin)
