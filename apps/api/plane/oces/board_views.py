# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Board column order: the order of state columns when work items are grouped by state.

GET  projects/{p}/oces/board-order/  {"state_ids": [...]}   members
PUT  projects/{p}/oces/board-order/  {"state_ids": [...]}   admins; [] goes back to upstream's order
"""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Project, State

from .models import ProjectFeature
from .property_views import ProjectScope


def clean_order(project, ids):
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValidationError({"state_ids": "Send a list of state ids."})
    if len(set(ids)) != len(ids):
        raise ValidationError({"state_ids": "Each state once."})
    known = {str(i) for i in State.objects.filter(project=project).values_list("id", flat=True)}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise ValidationError({"state_ids": "Not states of this project.", "unknown": unknown})
    return ids


class BoardOrderEndpoint(ProjectScope, AppAPIView):
    def get(self, request, slug, project_id):
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        row = ProjectFeature.objects.filter(project=project).first()
        return Response({"state_ids": row.board_state_order if row else []})

    def put(self, request, slug, project_id):
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        ids = clean_order(project, (request.data or {}).get("state_ids") if isinstance(request.data, dict) else None)
        try:
            with transaction.atomic():
                row, _ = ProjectFeature.objects.get_or_create(project=project)
        except IntegrityError:  # created by a parallel request
            row = ProjectFeature.objects.get(project=project)
        row.board_state_order = ids
        row.save(update_fields=["board_state_order", "updated_at"])
        return Response({"state_ids": ids})
