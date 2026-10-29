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
