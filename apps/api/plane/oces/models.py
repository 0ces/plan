# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.mixins import SoftDeletionManager
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


class _EntityManager(SoftDeletionManager):
    def __init__(self, entity):
        super().__init__()
        self.entity = entity

    def get_queryset(self):
        return super().get_queryset().filter(entity=self.entity)


class WorkItemProperty(BaseModel):
    """A custom field. Lives in a workspace, optionally a project; shown on the types it is linked to.

    entity=MODULE rows are module properties (project-level, values in ModulePropertyValue).
    `objects` only returns work item properties so module ones never show up on work items.
    """

    objects = _EntityManager("ISSUE")
    modules = _EntityManager("MODULE")
    all_objects = models.Manager()

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
    entity = models.CharField(max_length=16, default="ISSUE")

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


class ModulePropertyValue(BaseModel):
    """One value of a module property on a module. Multi-value properties have one row per value."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="+")
    module = models.ForeignKey("db.Module", on_delete=models.CASCADE, related_name="oces_property_values")
    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="module_values")
    value_text = models.TextField(null=True)
    value_boolean = models.BooleanField(null=True)
    value_decimal = models.DecimalField(max_digits=30, decimal_places=10, null=True)
    value_datetime = models.DateTimeField(null=True)
    value_uuid = models.UUIDField(null=True)
    value_option = models.ForeignKey(WorkItemPropertyOption, on_delete=models.CASCADE, null=True, related_name="+")
    external_source = models.CharField(max_length=255, null=True)
    external_id = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "oces_module_property_values"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["module", "property"], name="oces_mpv_module_idx"),
            models.Index(fields=["property", "value_uuid"], name="oces_mpv_uuid_idx"),
        ]


class Initiative(BaseModel):
    """A workspace goal that groups projects, epics and work items."""

    STATES = ("DRAFT", "PLANNED", "ACTIVE", "COMPLETED", "CLOSED")

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="oces_initiatives")
    name = models.CharField(max_length=255)
    description_html = models.TextField(blank=True, default="<p></p>")
    description_stripped = models.TextField(blank=True, default="")
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    state = models.CharField(max_length=16, default="DRAFT")
    lead = models.ForeignKey("db.User", on_delete=models.SET_NULL, null=True, related_name="+")
    logo_props = models.JSONField(default=dict)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "oces_initiatives"
        ordering = ("-created_at",)


class InitiativeProject(BaseModel):
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="project_links")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="oces_initiative_links")

    class Meta:
        db_table = "oces_initiative_projects"
        constraints = [models.UniqueConstraint(fields=["initiative", "project"], name="oces_initiative_project_unique")]


class InitiativeWorkItem(BaseModel):
    """A linked work item. as_epic marks links made through the epics endpoint (their children count too)."""

    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="work_item_links")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="oces_initiative_links")
    as_epic = models.BooleanField(default=False)

    class Meta:
        db_table = "oces_initiative_work_items"
        constraints = [
            models.UniqueConstraint(fields=["initiative", "issue", "as_epic"], name="oces_initiative_item_unique")
        ]


class InitiativeLabel(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="+")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=32, null=True)
    sort_order = models.FloatField(default=65535)
    initiatives = models.ManyToManyField(Initiative, related_name="labels", db_table="oces_initiative_label_links")

    class Meta:
        db_table = "oces_initiative_labels"
        ordering = ("sort_order", "name")


class WorkItemPage(BaseModel):
    """A page linked to a work item (CE has pages but no such link)."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="+")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="oces_page_links")
    page = models.ForeignKey("db.Page", on_delete=models.CASCADE, related_name="oces_work_item_links")

    class Meta:
        db_table = "oces_work_item_pages"
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "page"],
                condition=models.Q(deleted_at__isnull=True),
                name="oces_work_item_page_unique",
            )
        ]


class VersionStatus(BaseModel):
    """Last result of the GitHub release check (one row). See version.py."""

    fork_latest = models.CharField(max_length=64, null=True)
    upstream_latest = models.CharField(max_length=64, null=True)
    checked_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "oces_version_status"
