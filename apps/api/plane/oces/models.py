# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models import BaseModel


class WorkspaceFeature(BaseModel):
    """Workspace switches for features this fork implements (official API key names)."""

    workspace = models.OneToOneField("db.Workspace", on_delete=models.CASCADE, related_name="oces_features")
    initiatives = models.BooleanField(default=False)
    customers = models.BooleanField(default=False)
    releases = models.BooleanField(default=False)
    work_item_types = models.BooleanField(default=False)

    class Meta:
        db_table = "oces_workspace_features"


class ProjectFeature(BaseModel):
    """Project switches that have no column on upstream's Project model."""

    project = models.OneToOneField("db.Project", on_delete=models.CASCADE, related_name="oces_features")
    epics = models.BooleanField(default=False)
    workflows = models.BooleanField(default=False)

    class Meta:
        db_table = "oces_project_features"


class WorkItemProperty(BaseModel):
    """A custom field. Lives in a workspace, optionally a project; shown on the types it is linked to."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="oces_properties")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, null=True, related_name="oces_properties")
    # the type it was created under, if any (more types can be linked through WorkItemTypeProperty)
    issue_type = models.ForeignKey("db.IssueType", on_delete=models.SET_NULL, null=True, related_name="+")
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    logo_props = models.JSONField(default=dict)
    sort_order = models.FloatField(default=65535)
    property_type = models.CharField(max_length=32)
    relation_type = models.CharField(max_length=32, null=True)
    settings = models.JSONField(null=True)
    is_required = models.BooleanField(default=False)
    is_multi = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    default_value = models.JSONField(default=list)
    validation_rules = models.JSONField(null=True)
    external_source = models.CharField(max_length=255, null=True)
    external_id = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "oces_work_item_properties"
        ordering = ("sort_order", "created_at")


class WorkItemTypeProperty(BaseModel):
    """Which properties a work item type shows."""

    issue_type = models.ForeignKey("db.IssueType", on_delete=models.CASCADE, related_name="oces_property_links")
    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="type_links")

    class Meta:
        db_table = "oces_work_item_type_properties"
        constraints = [models.UniqueConstraint(fields=["issue_type", "property"], name="oces_type_property_unique")]


class WorkItemPropertyOption(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, null=True, related_name="+")
    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    sort_order = models.FloatField(default=65535)
    logo_props = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, related_name="children")
    external_source = models.CharField(max_length=255, null=True)
    external_id = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "oces_work_item_property_options"
        ordering = ("sort_order", "created_at")


class WorkItemPropertyValue(BaseModel):
    """One value of a property on a work item. Multi-value properties have one row per value."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="+")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="oces_property_values")
    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="values")
    value_text = models.TextField(null=True)
    value_boolean = models.BooleanField(null=True)
    value_decimal = models.DecimalField(max_digits=30, decimal_places=10, null=True)
    value_datetime = models.DateTimeField(null=True)
    value_uuid = models.UUIDField(null=True)
    value_option = models.ForeignKey(WorkItemPropertyOption, on_delete=models.CASCADE, null=True, related_name="+")
    external_source = models.CharField(max_length=255, null=True)
    external_id = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "oces_work_item_property_values"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["property", "value_option"], name="oces_pv_option_idx"),
            models.Index(fields=["property", "value_decimal"], name="oces_pv_decimal_idx"),
            models.Index(fields=["property", "value_datetime"], name="oces_pv_datetime_idx"),
            models.Index(fields=["property", "value_uuid"], name="oces_pv_uuid_idx"),
            models.Index(fields=["issue", "property"], name="oces_pv_issue_idx"),
        ]
