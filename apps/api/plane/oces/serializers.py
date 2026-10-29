# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import IssueType
from plane.db.models.issue_type import ProjectIssueType


class WorkItemTypeSerializer(serializers.ModelSerializer):
    """Official WorkItemType shape. is_default and project_ids come from the project links."""

    is_default = serializers.SerializerMethodField()
    project_ids = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()

    class Meta:
        model = IssueType
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
            "project_ids",
            "project",
            "workspace",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "is_default",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "deleted_at",
        ]

    def _links(self, obj):
        return list(ProjectIssueType.objects.filter(issue_type=obj).values_list("project_id", "is_default"))

    def get_project_ids(self, obj):
        return [str(pid) for pid, _ in self._links(obj)]

    def get_project(self, obj):
        project_id = self.context.get("project_id")
        return str(project_id) if project_id else None

    def get_is_default(self, obj):
        project_id = self.context.get("project_id")
        return any(str(pid) == str(project_id) and d for pid, d in self._links(obj)) if project_id else obj.is_default

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value
