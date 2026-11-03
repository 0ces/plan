# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Pages in the public API, at the paths and in the shapes the official SDK / MCP `page` tool uses.

CE has page models and web endpoints but no public API for them. The rules follow the web app
(plane/app/views/page/base.py and plane/app/permissions/page.py):
- project pages: project members only; a private page is for its owner only; guests see only
  their own pages unless the project lets guests see everything;
- workspace pages (pages with no project): workspace admins and members, never guests.
  CE's web app does not list them;
- locked or archived pages refuse edits; delete needs archive first; the owner or an admin
  archives, restores and deletes.
Collections are a paid-edition feature with no CE model, so collection_id is refused.
"""

import uuid
from datetime import date, datetime

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.app.permissions.page import ProjectPagePermission
from plane.app.views.page.base import unarchive_archive_page_and_descendants
from plane.bgtasks.page_transaction_task import page_transaction
from plane.db.models import (
    Issue,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    UserFavorite,
    UserRecentVisit,
    Workspace,
    WorkspaceMember,
)
from plane.utils.content_validator import validate_html_content

from .models import WorkItemPage
from .page_content import LiveUnavailable, render
from .pql_views import visible_work_items

ADMIN, MEMBER, GUEST = 20, 15, 5


class LiveDown(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = {"error": "The live collaboration service is unreachable, so nothing was written. Try again."}


def _uuid(name, value):
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise ValidationError({name: "Must be a UUID."})


def workspace_role(user, slug):
    return (
        WorkspaceMember.objects.filter(workspace__slug=slug, member=user, is_active=True)
        .values_list("role", flat=True)
        .first()
    )


def readable_pages(user, slug):
    """Every page this user may open in the workspace, project or workspace scope."""
    members = ProjectMember.objects.filter(
        member=user, workspace__slug=slug, is_active=True, project__archived_at__isnull=True
    )
    full = members.filter(Q(role__gte=MEMBER) | Q(project__guest_view_all_features=True)).values("project_id")
    shared = Q(owned_by=user) | Q(access=Page.PUBLIC_ACCESS)
    in_full = ProjectPage.objects.filter(project_id__in=full).values("page_id")
    in_any = ProjectPage.objects.filter(project_id__in=members.values("project_id")).values("page_id")
    q = (Q(id__in=in_full) & shared) | Q(id__in=in_any, owned_by=user)
    if (workspace_role(user, slug) or 0) >= MEMBER:
        ever_linked = ProjectPage.all_objects.filter(workspace__slug=slug).values("page_id")
        q |= ~Q(id__in=ever_linked) & shared
    return Page.objects.filter(workspace__slug=slug).filter(q)


def page_out(page):
    return {
        "id": str(page.id),
        "name": page.name,
        "description_html": page.description_html,
        "description_stripped": page.description_stripped,
        "owned_by": str(page.owned_by_id),
        "workspace": str(page.workspace_id),
        "projects": [str(link.project_id) for link in page.project_pages.all()],
        "access": page.access,
        "color": page.color,
        "is_locked": page.is_locked,
        "archived_at": page.archived_at.isoformat() if page.archived_at else None,
        "parent_id": str(page.parent_id) if page.parent_id else None,
        "collection_id": None,
        "page_collection_id": None,
        "logo_props": page.logo_props,
        "view_props": page.view_props,
        "sort_order": page.sort_order,
        "external_id": page.external_id,
        "external_source": page.external_source,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
        "created_by": str(page.created_by_id) if page.created_by_id else None,
        "updated_by": str(page.updated_by_id) if page.updated_by_id else None,
    }


def clean_page(data, creating):
    """Validated model fields, plus the sanitized HTML body (None when not sent)."""
    if not isinstance(data, dict):
        raise ValidationError({"error": "Send a JSON object."})
    out = {}
    if creating or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError({"name": "A page needs a name."})
        out["name"] = name.strip()
    if "access" in data and data["access"] is not None:
        if data["access"] not in (Page.PUBLIC_ACCESS, Page.PRIVATE_ACCESS):
            raise ValidationError({"access": "Use 0 (public) or 1 (private)."})
        out["access"] = data["access"]
    if "is_locked" in data and data["is_locked"] is not None:
        if not isinstance(data["is_locked"], bool):
            raise ValidationError({"is_locked": "Must be true or false."})
        out["is_locked"] = data["is_locked"]
    for key in ("color", "external_id", "external_source"):
        if key in data:
            if data[key] is not None and not isinstance(data[key], str):
                raise ValidationError({key: "Must be text."})
            out[key] = data[key] or ("" if key == "color" else None)
    for key in ("logo_props", "view_props"):
        if key in data and data[key] is not None:
            if not isinstance(data[key], dict):
                raise ValidationError({key: "Must be an object."})
            out[key] = data[key]
    html = data.get("description_html")
    if html is not None:
        if not isinstance(html, str):
            raise ValidationError({"description_html": "Must be HTML text."})
        ok, error, clean = validate_html_content(html)
        if not ok:
            raise ValidationError({"description_html": error})
        html = clean if clean is not None else html
    return out, html


def write_content(page, html):
    """Store HTML as the editor document (binary + html + json), converted by the live server."""
    try:
        formats = render(page.id, page.name, html or "<p></p>")
    except LiveUnavailable:
        raise LiveDown()
    for key, value in formats.items():
        setattr(page, key, value)
    page.save()


# ---------------------------------------------------------------- scopes


class WorkspacePagePermission(BasePermission):
    """Workspace pages: admins and members; guests never."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return (workspace_role(request.user, view.kwargs["slug"]) or 0) >= MEMBER


class ProjectPagesPermission(ProjectPagePermission):
    """CE's page rules, but a page that is not in the project is the view's 404, not a 403."""

    def has_permission(self, request, view):
        kw = view.kwargs
        page_id = kw.get("page_id")
        if (
            page_id
            and not Page.objects.filter(
                id=page_id, project_pages__project_id=kw["project_id"], project_pages__deleted_at__isnull=True
            ).exists()
        ):
            return self._check_project_member_access(request, kw["slug"], kw["project_id"]) is not None
        return super().has_permission(request, view)


class ProjectScope:
    permission_classes = [ProjectPagesPermission]

    def project(self):
        if not hasattr(self, "_project"):
            self._project = get_object_or_404(
                Project, pk=self.kwargs["project_id"], workspace__slug=self.kwargs["slug"], archived_at__isnull=True
            )
        return self._project

    def role(self):
        return (
            ProjectMember.objects.filter(project=self.project(), member=self.request.user, is_active=True)
            .values_list("role", flat=True)
            .first()
        )

    def pages(self):
        linked = ProjectPage.objects.filter(project=self.project()).values("page_id")
        return readable_pages(self.request.user, self.kwargs["slug"]).filter(id__in=linked)

    def attach(self, page):
        ProjectPage.objects.create(workspace_id=page.workspace_id, project=self.project(), page=page)


class WorkspaceScope:
    permission_classes = [WorkspacePagePermission]

    def project(self):
        return None

    def role(self):
        return workspace_role(self.request.user, self.kwargs["slug"])

    def pages(self):
        ever_linked = ProjectPage.all_objects.filter(workspace__slug=self.kwargs["slug"]).values("page_id")
        return readable_pages(self.request.user, self.kwargs["slug"]).exclude(id__in=ever_linked)

    def attach(self, page):
        pass


class PageBase:
    def page(self, page_id):
        page = self.pages().prefetch_related("project_pages").filter(pk=page_id).first()
        if page is None:
            raise NotFound({"error": "Page not found"})
        return page

    def owner_or_admin(self, page, action):
        if page.owned_by_id != self.request.user.id and self.role() != ADMIN:
            raise PermissionDenied({"error": f"Only the owner or an admin can {action} this page."})

    def workspace_id(self):
        project = self.project()
        if project:
            return project.workspace_id
        return get_object_or_404(Workspace, slug=self.kwargs["slug"]).id


# ---------------------------------------------------------------- endpoints


class PageListMixin(PageBase):
    def get(self, request, slug, project_id=None):
        qs = self.pages().prefetch_related("project_pages")
        if request.query_params.get("parent_id"):
            qs = qs.filter(parent_id=_uuid("parent_id", request.query_params["parent_id"]))
        return self.paginate(
            request=request,
            queryset=qs.order_by("-created_at"),
            on_results=lambda pages: [page_out(p) for p in pages],
        )

    def post(self, request, slug, project_id=None):
        fields, html = clean_page(request.data, creating=True)
        if request.data.get("collection_id"):
            raise ValidationError({"collection_id": "Collections are not available on this instance."})
        parent = None
        if request.data.get("parent_id"):
            try:
                parent = self.page(_uuid("parent_id", request.data["parent_id"]))
            except NotFound:
                raise ValidationError({"parent_id": "Parent page not found here."})
            if parent.archived_at:
                raise ValidationError({"parent_id": "The parent page is archived."})
        with transaction.atomic():
            page = Page.objects.create(workspace_id=self.workspace_id(), owned_by=request.user, parent=parent, **fields)
            self.attach(page)
            write_content(page, html)
        page_transaction.delay(
            new_description_html=page.description_html, old_description_html=None, page_id=str(page.id)
        )
        return Response(page_out(self.page(page.id)), status=status.HTTP_201_CREATED)


class PageDetailMixin(PageBase):
    def get(self, request, slug, page_id, project_id=None):
        return Response(page_out(self.page(page_id)))

    def put(self, request, slug, page_id, project_id=None):
        page = self.page(page_id)
        fields, html = clean_page(request.data, creating=False)
        if page.archived_at:
            raise ValidationError({"error": "Page is archived", "error_code": "PAGE_ARCHIVED"})
        # a locked page takes no edits, except being unlocked
        if page.is_locked and (html is not None or set(fields) - {"is_locked"}):
            raise ValidationError({"error": "Page is locked", "error_code": "PAGE_LOCKED"})
        if fields.get("access", page.access) != page.access and page.owned_by_id != request.user.id:
            raise ValidationError({"access": "Only the page owner can change its access."})
        old_html = page.description_html
        with transaction.atomic():
            for key, value in fields.items():
                setattr(page, key, value)
            if html is None:
                page.save()
            else:
                write_content(page, html)
        if html is not None:
            page_transaction.delay(
                new_description_html=page.description_html, old_description_html=old_html, page_id=str(page.id)
            )
        return Response(page_out(self.page(page.id)))

    patch = put

    def delete(self, request, slug, page_id, project_id=None):
        page = self.page(page_id)
        if page.archived_at is None:
            raise ValidationError({"error": "The page should be archived before deleting"})
        self.owner_or_admin(page, "delete")
        Page.objects.filter(parent_id=page.id).update(parent=None)
        page.delete()
        UserFavorite.objects.filter(workspace__slug=slug, entity_identifier=page_id, entity_type="page").delete()
        UserRecentVisit.objects.filter(workspace__slug=slug, entity_identifier=page_id, entity_name="page").delete(
            soft=False
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PageArchiveMixin(PageBase):
    def post(self, request, slug, page_id, project_id=None):
        page = self.page(page_id)
        self.owner_or_admin(page, "archive")
        UserFavorite.objects.filter(workspace__slug=slug, entity_identifier=page_id, entity_type="page").delete()
        unarchive_archive_page_and_descendants(page_id, datetime.now())
        return Response({"archived_at": date.today().isoformat()})

    def delete(self, request, slug, page_id, project_id=None):
        page = self.page(page_id)
        self.owner_or_admin(page, "restore")
        # restoring under an archived parent would break the tree
        if page.parent_id and page.parent.archived_at:
            page.parent = None
            page.save(update_fields=["parent"])
        unarchive_archive_page_and_descendants(page_id, None)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _views(mixin):
    name = mixin.__name__.replace("Mixin", "")
    project = type("Project" + name + "APIEndpoint", (ProjectScope, mixin, BaseAPIView), {})
    workspace = type("Workspace" + name + "APIEndpoint", (WorkspaceScope, mixin, BaseAPIView), {})
    return project, workspace


ProjectPageListAPIEndpoint, WorkspacePageListAPIEndpoint = _views(PageListMixin)
ProjectPageDetailAPIEndpoint, WorkspacePageDetailAPIEndpoint = _views(PageDetailMixin)
ProjectPageArchiveAPIEndpoint, WorkspacePageArchiveAPIEndpoint = _views(PageArchiveMixin)


# ---------------------------------------------------------------- work item <-> page links


class ProjectMemberWrites(BasePermission):
    """Any project member reads; admins and members link and unlink."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        role = (
            ProjectMember.objects.filter(
                project_id=view.kwargs["project_id"],
                workspace__slug=view.kwargs["slug"],
                member=request.user,
                is_active=True,
            )
            .values_list("role", flat=True)
            .first()
        )
        if role is None:
            return False
        return request.method in SAFE_METHODS or role >= MEMBER


def link_out(link):
    page = link.page
    return {
        "id": str(link.id),
        "page": {
            "id": str(page.id),
            "name": page.name,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
            "created_by": str(page.created_by_id) if page.created_by_id else None,
            "is_global": page.is_global,
            "logo_props": page.logo_props,
        },
        "issue": str(link.issue_id),
        "project": str(link.project_id),
        "workspace": str(link.workspace_id),
        "created_at": link.created_at,
        "updated_at": link.updated_at,
        "created_by": str(link.created_by_id) if link.created_by_id else None,
    }


class WorkItemPageBase(BaseAPIView):
    permission_classes = [ProjectMemberWrites]

    def issue(self):
        qs = visible_work_items(Issue.issue_objects.all(), self.request.user, self.kwargs["slug"])
        return get_object_or_404(qs, pk=self.kwargs["issue_id"], project_id=self.kwargs["project_id"])

    def links(self, issue):
        readable = readable_pages(self.request.user, self.kwargs["slug"]).values("id")
        return WorkItemPage.objects.filter(issue=issue, page_id__in=readable).select_related("page")


class WorkItemPageListAPIEndpoint(WorkItemPageBase):
    def get(self, request, slug, project_id, issue_id):
        return self.paginate(
            request=request,
            queryset=self.links(self.issue()).order_by("-created_at"),
            on_results=lambda links: [link_out(x) for x in links],
        )

    def post(self, request, slug, project_id, issue_id):
        issue = self.issue()
        page_id = _uuid("page_id", request.data.get("page_id") if isinstance(request.data, dict) else None)
        page = readable_pages(request.user, slug).filter(pk=page_id).first()
        if page is None:
            raise ValidationError({"page_id": "Page not found."})
        link, created = WorkItemPage.objects.get_or_create(
            issue=issue, page=page, defaults={"workspace_id": issue.workspace_id, "project_id": issue.project_id}
        )
        return Response(link_out(link), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WorkItemPageDetailAPIEndpoint(WorkItemPageBase):
    def link(self, link_id):
        return get_object_or_404(self.links(self.issue()), pk=link_id)

    def get(self, request, slug, project_id, issue_id, link_id):
        return Response(link_out(self.link(link_id)))

    def delete(self, request, slug, project_id, issue_id, link_id):
        self.link(link_id).delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
