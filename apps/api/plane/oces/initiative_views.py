# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Initiatives: workspace goals that group projects, epics and work items.

Paths and shapes follow the official public API (docs/fork/api-contract.md, section c).
Guests never see initiatives; workspace members and admins do.
"""

import uuid
from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from plane.api.serializers import IssueSerializer, ProjectSerializer
from plane.api.views.base import BaseAPIView as PublicAPIView
from plane.app.views.base import BaseAPIView as AppAPIView
from plane.db.models import Issue, Project, ProjectMember, Workspace, WorkspaceMember
from plane.utils.content_validator import validate_html_content

from .models import Initiative, InitiativeLabel, InitiativeProject, InitiativeWorkItem
from .pql_views import visible_work_items

GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


class WorkspaceMemberNotGuest(BasePermission):
    """Initiatives span projects, so guests (role 5) never see them."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return WorkspaceMember.objects.filter(
            workspace__slug=view.kwargs["slug"], member=request.user, is_active=True, role__gte=15
        ).exists()


def _err(message, **extra):
    raise ValidationError({"error": message, **extra})


def _date(name, value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValidationError({name: "Use a date like 2026-10-30."})


def clean_initiative(data, workspace, instance=None):
    if not isinstance(data, dict):
        _err("Send a JSON object.")
    out = {}
    if instance is None or "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "name is required."})
        out["name"] = name[:255]
    if "description_html" in data:
        ok, error, clean = validate_html_content(data.get("description_html") or "")
        if not ok:
            raise ValidationError({"description_html": error})
        out["description_html"] = clean or "<p></p>"
        out["description_stripped"] = strip_tags(out["description_html"]).strip()
    for key in ("start_date", "end_date"):
        if key in data:
            out[key] = _date(key, data[key])
    start = out.get("start_date", instance.start_date if instance else None)
    end = out.get("end_date", instance.end_date if instance else None)
    if start and end and start > end:
        raise ValidationError({"end_date": "end_date must be on or after start_date."})
    if "state" in data:
        if data["state"] not in Initiative.STATES:
            raise ValidationError({"state": f"state must be one of {list(Initiative.STATES)}."})
        out["state"] = data["state"]
    if "lead" in data:
        lead = data["lead"] or None
        if lead and not WorkspaceMember.objects.filter(workspace=workspace, member_id=lead, is_active=True).exists():
            raise ValidationError({"lead": "lead must be a member of this workspace."})
        out["lead_id"] = lead
    if "logo_props" in data:
        if not isinstance(data["logo_props"], dict):
            raise ValidationError({"logo_props": "logo_props must be an object."})
        out["logo_props"] = data["logo_props"]
    return out


def initiative_out(i):
    return {
        "id": str(i.id),
        "name": i.name,
        "description": i.description_stripped,
        "description_html": i.description_html,
        "description_stripped": i.description_stripped,
        "description_binary": None,
        "start_date": i.start_date.isoformat() if i.start_date else None,
        "end_date": i.end_date.isoformat() if i.end_date else None,
        "logo_props": i.logo_props or {},
        "state": i.state,
        "lead": str(i.lead_id) if i.lead_id else None,
        "label_ids": [str(x) for x in i.labels.values_list("id", flat=True)],
        "workspace": str(i.workspace_id),
        "created_at": i.created_at,
        "updated_at": i.updated_at,
        "created_by": str(i.created_by_id) if i.created_by_id else None,
        "updated_by": str(i.updated_by_id) if i.updated_by_id else None,
        "deleted_at": None,
    }


def label_out(lb):
    return {
        "id": str(lb.id),
        "name": lb.name,
        "description": lb.description,
        "color": lb.color,
        "sort_order": lb.sort_order,
        "workspace": str(lb.workspace_id),
        "created_at": lb.created_at,
        "updated_at": lb.updated_at,
        "deleted_at": None,
    }


def my_project_ids(user, slug):
    return ProjectMember.objects.filter(
        member=user, workspace__slug=slug, is_active=True, project__archived_at__isnull=True
    ).values("project_id")


def rollup_items(initiative, user, slug):
    """Work items an initiative covers, as the caller can see them, without duplicates:
    every item in linked projects, linked work items, and the children of linked epics."""
    links = InitiativeWorkItem.objects.filter(initiative=initiative)
    projects = InitiativeProject.objects.filter(initiative=initiative).values("project_id")
    scope = (
        Q(project_id__in=projects)
        | Q(id__in=links.filter(as_epic=False).values("issue_id"))
        | Q(parent_id__in=links.filter(as_epic=True).values("issue_id"))
    )
    return visible_work_items(Issue.issue_objects.filter(scope), user, slug)


def progress(initiative, user, slug):
    counts = dict(
        rollup_items(initiative, user, slug).values_list("state__group").annotate(n=Count("id", distinct=True))
    )
    out = {f"{g}_issues": counts.get(g, 0) for g in GROUPS}
    out["total_issues"] = sum(counts.get(g, 0) for g in GROUPS)
    return out


class Base:
    public = False

    def get_permissions(self):
        return [WorkspaceMemberNotGuest()]

    def workspace(self, slug):
        return get_object_or_404(Workspace, slug=slug)

    def initiative(self, slug, initiative_id):
        return get_object_or_404(Initiative, workspace__slug=slug, pk=initiative_id)

    def ids(self, key):
        raw = self.request.data.get(key) if isinstance(self.request.data, dict) else None
        if not isinstance(raw, list) or not raw:
            raise ValidationError({key: f"Send a non-empty list in {key}."})
        try:
            return list(dict.fromkeys(str(uuid.UUID(str(x))) for x in raw))
        except ValueError:
            raise ValidationError({key: "Ids must be UUIDs."})

    def with_extras(self, i):
        """Internal API extras for the web app: progress and linked ids."""
        data = initiative_out(i)
        if not self.public:
            slug = self.kwargs["slug"]
            mine = my_project_ids(self.request.user, slug)
            data["project_ids"] = [
                str(x) for x in i.project_links.filter(project_id__in=mine).values_list("project_id", flat=True)
            ]
            visible = visible_work_items(Issue.issue_objects.all(), self.request.user, slug).values("id")
            links = i.work_item_links.filter(issue_id__in=visible)
            data["epic_ids"] = [str(x) for x in links.filter(as_epic=True).values_list("issue_id", flat=True)]
            data["work_item_ids"] = [str(x) for x in links.filter(as_epic=False).values_list("issue_id", flat=True)]
            data["progress"] = progress(i, self.request.user, slug)
        return data


# ---------------------------------------------------------------- initiatives


class InitiativeListMixin(Base):
    def get(self, request, slug):
        qs = Initiative.objects.filter(workspace__slug=slug).select_related("workspace")
        return Response({"results": [self.with_extras(i) for i in qs], "total_count": qs.count()})

    def post(self, request, slug):
        workspace = self.workspace(slug)
        fields = clean_initiative(request.data, workspace)
        initiative = Initiative.objects.create(workspace=workspace, **fields)
        return Response(self.with_extras(initiative), status=status.HTTP_201_CREATED)


class InitiativeDetailMixin(Base):
    def get(self, request, slug, initiative_id):
        return Response(self.with_extras(self.initiative(slug, initiative_id)))

    def patch(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        for k, v in clean_initiative(request.data, initiative.workspace, initiative).items():
            setattr(initiative, k, v)
        initiative.save()
        return Response(self.with_extras(initiative))

    def delete(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        is_admin = WorkspaceMember.objects.filter(
            workspace__slug=slug, member=request.user, is_active=True, role=20
        ).exists()
        if not is_admin and initiative.created_by_id != request.user.id:
            return Response({"error": "Only workspace admins or the creator can delete an initiative."}, status=403)
        with transaction.atomic():
            initiative.labels.clear()
            initiative.project_links.all().delete(soft=False)
            initiative.work_item_links.all().delete(soft=False)
            initiative.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InitiativeProjectsMixin(Base):
    def _projects(self, initiative):
        mine = my_project_ids(self.request.user, initiative.workspace.slug)
        return Project.objects.filter(oces_initiative_links__initiative=initiative, id__in=mine)

    def get(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        qs = self._projects(initiative).order_by("name")
        if not self.public:
            return Response(ProjectSerializer(qs, many=True).data)
        return self.paginate(
            request=request,
            queryset=qs,
            on_results=lambda projects: ProjectSerializer(
                projects, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        ids = self.ids("project_ids")
        mine = my_project_ids(request.user, slug)
        found = list(Project.objects.filter(workspace__slug=slug, id__in=ids).filter(id__in=mine))
        if len(found) != len(ids):
            _err("Some projects do not exist or you are not a member of them.")
        for p in found:
            InitiativeProject.objects.get_or_create(initiative=initiative, project=p)
        return Response(ProjectSerializer(found, many=True).data, status=status.HTTP_201_CREATED)

    def delete(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        InitiativeProject.objects.filter(initiative=initiative, project_id__in=self.ids("project_ids")).delete(
            soft=False
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InitiativeItemsMixin(Base):
    """work-items/ and epics/: the same links, kept apart by as_epic."""

    as_epic = False
    key = "work_item_ids"

    def _visible(self, slug):
        return visible_work_items(Issue.issue_objects.all(), self.request.user, slug)

    def get(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        linked = InitiativeWorkItem.objects.filter(initiative=initiative, as_epic=self.as_epic).values("issue_id")
        qs = self._visible(slug).filter(id__in=linked).select_related("project", "state").order_by("-created_at")
        if not self.public:
            return Response(IssueSerializer(qs, many=True).data)
        return self.paginate(
            request=request,
            queryset=qs,
            on_results=lambda items: IssueSerializer(items, many=True, fields=self.fields, expand=self.expand).data,
        )

    def post(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        ids = self.ids(self.key)
        found = list(self._visible(slug).filter(id__in=ids))
        if len(found) != len(ids):
            _err("Some work items do not exist or you cannot see them.")
        for item in found:
            InitiativeWorkItem.objects.get_or_create(initiative=initiative, issue=item, as_epic=self.as_epic)
        return Response(IssueSerializer(found, many=True).data, status=status.HTTP_201_CREATED)

    def delete(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        InitiativeWorkItem.objects.filter(
            initiative=initiative, as_epic=self.as_epic, issue_id__in=self.ids(self.key)
        ).delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InitiativeEpicsMixin(InitiativeItemsMixin):
    as_epic = True
    key = "epic_ids"


# ---------------------------------------------------------------- labels


def clean_label(data, workspace, instance=None):
    if not isinstance(data, dict):
        _err("Send a JSON object.")
    out = {k: data[k] for k in ("description", "color", "sort_order") if k in data}
    if instance is None or "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "name is required."})
        clash = InitiativeLabel.objects.filter(workspace=workspace, name__iexact=name)
        if instance:
            clash = clash.exclude(pk=instance.pk)
        if clash.exists():
            raise ValidationError({"name": "A label with this name already exists."})
        out["name"] = name[:255]
    return out


class LabelListMixin(Base):
    def get(self, request, slug):
        return Response({"results": [label_out(lb) for lb in InitiativeLabel.objects.filter(workspace__slug=slug)]})

    def post(self, request, slug):
        workspace = self.workspace(slug)
        label = InitiativeLabel.objects.create(workspace=workspace, **clean_label(request.data, workspace))
        return Response(label_out(label), status=status.HTTP_201_CREATED)


class LabelDetailMixin(Base):
    def _get(self, slug, label_id):
        return get_object_or_404(InitiativeLabel, workspace__slug=slug, pk=label_id)

    def get(self, request, slug, label_id):
        return Response(label_out(self._get(slug, label_id)))

    def patch(self, request, slug, label_id):
        label = self._get(slug, label_id)
        for k, v in clean_label(request.data, label.workspace, label).items():
            setattr(label, k, v)
        label.save()
        return Response(label_out(label))

    def delete(self, request, slug, label_id):
        label = self._get(slug, label_id)
        label.initiatives.clear()
        label.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InitiativeLabelsMixin(Base):
    def get(self, request, slug, initiative_id):
        return Response({"results": [label_out(lb) for lb in self.initiative(slug, initiative_id).labels.all()]})

    def post(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        ids = self.ids("label_ids")
        found = list(InitiativeLabel.objects.filter(workspace__slug=slug, id__in=ids))
        if len(found) != len(ids):
            _err("Some labels do not exist in this workspace.")
        initiative.labels.add(*found)
        return Response([label_out(lb) for lb in found], status=status.HTTP_201_CREATED)

    def delete(self, request, slug, initiative_id):
        initiative = self.initiative(slug, initiative_id)
        initiative.labels.remove(*InitiativeLabel.objects.filter(workspace__slug=slug, id__in=self.ids("label_ids")))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- concrete views


def _pair(mixin):
    name = mixin.__name__.replace("Mixin", "")
    public = type(name + "APIEndpoint", (mixin, PublicAPIView), {"public": True})
    internal = type(name + "Endpoint", (mixin, AppAPIView), {"public": False})
    return public, internal


InitiativeListAPIEndpoint, InitiativeListEndpoint = _pair(InitiativeListMixin)
InitiativeDetailAPIEndpoint, InitiativeDetailEndpoint = _pair(InitiativeDetailMixin)
InitiativeProjectsAPIEndpoint, InitiativeProjectsEndpoint = _pair(InitiativeProjectsMixin)
InitiativeItemsAPIEndpoint, InitiativeItemsEndpoint = _pair(InitiativeItemsMixin)
InitiativeEpicsAPIEndpoint, InitiativeEpicsEndpoint = _pair(InitiativeEpicsMixin)
LabelListAPIEndpoint, LabelListEndpoint = _pair(LabelListMixin)
LabelDetailAPIEndpoint, LabelDetailEndpoint = _pair(LabelDetailMixin)
InitiativeLabelsAPIEndpoint, InitiativeLabelsEndpoint = _pair(InitiativeLabelsMixin)
