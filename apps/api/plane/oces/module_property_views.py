# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Module property endpoints, shaped like the project-flat work item property ones.

projects/{p}/module-properties/[{id}/]                    definitions (admins write)
projects/{p}/module-properties/{id}/options/[{oid}/]      dropdown options
projects/{p}/modules/{m}/module-properties/{id}/values/   one property's value on a module
projects/{p}/modules/{m}/module-property-values/          all values + computed progress
projects/{p}/module-property-values/                      all values of every module (list view)
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Module

from . import module_properties as M
from . import properties as P
from .models import WorkItemProperty
from .property_views import OptionsMixin, ProjectScope, _pair, property_out


def module_property_out(p):
    out = property_out(p)
    for k in ("issue_type", "issue_type_ids"):
        out.pop(k)
    out["entity"] = "MODULE"
    return out


class ModuleScope(ProjectScope):
    def project_props(self, project):
        return WorkItemProperty.modules.filter(project=project)


class ModulePropertyListMixin(ModuleScope):
    def get(self, request, slug, project_id):
        qs = self.project_props(self.project(slug, project_id)).prefetch_related("options")
        return Response([module_property_out(p) for p in qs])

    def post(self, request, slug, project_id):
        project = self.project(slug, project_id)
        prop = P.create_property(
            workspace_id=project.workspace_id,
            project_id=project.id,
            issue_type=None,
            data=request.data,
            scope_qs=self.project_props(project),
            entity="MODULE",
        )
        return Response(module_property_out(prop), status=status.HTTP_201_CREATED)


class ModulePropertyDetailMixin(ModuleScope):
    def _get(self, slug, project_id, property_id):
        return get_object_or_404(self.project_props(self.project(slug, project_id)), pk=property_id)

    def get(self, request, slug, project_id, property_id):
        return Response(module_property_out(self._get(slug, project_id, property_id)))

    @transaction.atomic
    def patch(self, request, slug, project_id, property_id):
        prop = self._get(slug, project_id, property_id)
        prop = P.update_property(prop, request.data, self.project_props(prop.project))
        if isinstance(request.data, dict) and request.data.get("options") is not None:
            P.replace_options(prop, request.data["options"])  # the MCP sends the whole list
        return Response(module_property_out(prop))

    def delete(self, request, slug, project_id, property_id):
        P.delete_property(self._get(slug, project_id, property_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModuleOptionsMixin(OptionsMixin, ModuleScope):
    def prop(self, slug, project_id, property_id):
        prop = get_object_or_404(self.project_props(self.project(slug, project_id)), pk=property_id)
        if prop.property_type != "OPTION":
            raise ValidationError({"error": "Only OPTION properties have options."})
        return prop


class ModuleValuesMixin:
    def get_permissions(self):
        return [ProjectEntityPermission()]

    def module(self, slug, project_id, module_id):
        return get_object_or_404(Module.objects, pk=module_id, project_id=project_id, workspace__slug=slug)

    def _load(self, slug, project_id, module_id, property_id):
        module = self.module(slug, project_id, module_id)
        prop = get_object_or_404(WorkItemProperty.modules.filter(project_id=project_id), pk=property_id)
        return module, prop

    def get(self, request, slug, project_id, module_id, property_id):
        module, prop = self._load(slug, project_id, module_id, property_id)
        rows = M.rows_for(prop, module)
        if not rows:
            return Response({"error": "No value set for this property."}, status=status.HTTP_404_NOT_FOUND)
        return Response(M.values_response(prop, rows))

    def _write(self, request, slug, project_id, module_id, property_id, must_exist):
        module, prop = self._load(slug, project_id, module_id, property_id)
        if not prop.is_active:
            return Response({"error": "This property is not active."}, status=400)
        if not isinstance(request.data, dict) or "value" not in request.data:
            return Response({"value": "value is required."}, status=400)
        existed = prop.module_values.filter(module=module).exists()
        if must_exist and not existed:
            return Response({"error": "No value set for this property."}, status=status.HTTP_404_NOT_FOUND)
        external = {k: request.data[k] for k in ("external_id", "external_source") if request.data.get(k)}
        rows = M.set_values(prop, module, request.data["value"], external)
        code = status.HTTP_200_OK if existed else status.HTTP_201_CREATED
        return Response(M.values_response(prop, rows), status=code)

    def post(self, request, slug, project_id, module_id, property_id):
        return self._write(request, slug, project_id, module_id, property_id, must_exist=False)

    def patch(self, request, slug, project_id, module_id, property_id):
        return self._write(request, slug, project_id, module_id, property_id, must_exist=True)

    def delete(self, request, slug, project_id, module_id, property_id):
        module, prop = self._load(slug, project_id, module_id, property_id)
        M.clear_values(prop, module)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModuleAllValuesMixin(ModuleValuesMixin):
    def get(self, request, slug, project_id, module_id):
        module = self.module(slug, project_id, module_id)
        return Response(
            {
                "module_id": str(module.id),
                "values": M.all_values([module.id])[str(module.id)],
                "computed": M.computed(module),
            }
        )


class ProjectModuleValuesMixin(ModuleValuesMixin):
    def get(self, request, slug, project_id):
        ids = list(Module.objects.filter(project_id=project_id, workspace__slug=slug).values_list("id", flat=True))
        return Response(M.all_values(ids))


ModulePropertyListAPIEndpoint, ModulePropertyListEndpoint = _pair(ModulePropertyListMixin)
ModulePropertyDetailAPIEndpoint, ModulePropertyDetailEndpoint = _pair(ModulePropertyDetailMixin)
ModuleOptionsAPIEndpoint, ModuleOptionsEndpoint = _pair(ModuleOptionsMixin)
ModuleValuesAPIEndpoint, ModuleValuesEndpoint = _pair(ModuleValuesMixin)
ModuleAllValuesAPIEndpoint, ModuleAllValuesEndpoint = _pair(ModuleAllValuesMixin)
ProjectModuleValuesAPIEndpoint, ProjectModuleValuesEndpoint = _pair(ProjectModuleValuesMixin)
