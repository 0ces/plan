# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Estimate, EstimatePoint, Issue, Module, ModuleIssue, State, User, WorkspaceMember
from plane.oces.models import WorkItemProperty

from .test_work_item_types import make_project


@pytest.fixture
def project(db, workspace, create_user):
    return make_project(workspace, create_user, "MP")


@pytest.fixture
def modules(project, create_user):
    make = lambda name: Module.objects.create(  # noqa: E731
        name=name, project=project, workspace=project.workspace, created_by=create_user
    )
    return make("E01"), make("E02")


def v1(project, path=""):
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def create(client, project, body):
    res = client.post(v1(project, "module-properties/"), body, format="json")
    assert res.status_code == 201, res.content
    return res.json()


@pytest.mark.contract
class TestModuleProperties:
    def test_definitions_and_values(self, api_key_client, project, modules):
        e01, e02 = modules
        prio = create(
            api_key_client,
            project,
            {"display_name": "Prioridad", "property_type": "OPTION", "options": [{"name": "P1"}, {"name": "P2"}]},
        )
        deps = create(
            api_key_client,
            project,
            {"display_name": "Depende de", "property_type": "RELATION", "relation_type": "MODULE", "is_multi": True},
        )
        order = create(api_key_client, project, {"display_name": "Orden sugerido", "property_type": "DECIMAL"})
        assert prio["entity"] == "MODULE" and "issue_type_ids" not in prio
        listed = api_key_client.get(v1(project, "module-properties/")).json()
        assert [p["display_name"] for p in listed] == ["Prioridad", "Depende de", "Orden sugerido"]

        # module properties never show up as work item properties
        assert api_key_client.get(v1(project, "work-item-properties/")).json() == []
        ws = f"/api/v1/workspaces/{project.workspace.slug}/work-item-properties/"
        assert api_key_client.get(ws).json() == []

        val = lambda m, p: v1(project, f"modules/{m.id}/module-properties/{p['id']}/values/")  # noqa: E731
        p1 = prio["options"][0]["id"]
        res = api_key_client.post(val(e01, prio), {"value": p1}, format="json")
        assert res.status_code == 201 and res.json()["value"] == p1 and res.json()["module_id"] == str(e01.id)
        assert api_key_client.post(val(e01, prio), {"value": p1}, format="json").status_code == 200
        res = api_key_client.post(val(e02, deps), {"value": [str(e01.id)]}, format="json")
        assert res.status_code == 201 and [v["value"] for v in res.json()] == [str(e01.id)]
        assert api_key_client.post(val(e01, deps), {"value": [str(e01.id)]}, format="json").status_code == 400
        assert api_key_client.post(val(e01, order), {"value": 3}, format="json").json()["value"] == 3.0

        everything = api_key_client.get(v1(project, "module-property-values/")).json()
        assert everything[str(e01.id)] == {prio["id"]: p1, order["id"]: 3.0}
        assert everything[str(e02.id)] == {deps["id"]: [str(e01.id)]}

        assert api_key_client.delete(val(e01, order)).status_code == 204
        assert api_key_client.get(val(e01, order)).status_code == 404

        # options endpoint, and deleting the definition removes its values
        opts = v1(project, f"module-properties/{prio['id']}/options/")
        assert api_key_client.post(opts, {"name": "P3"}, format="json").status_code == 201
        assert len(api_key_client.get(opts).json()) == 3
        # PATCH with options replaces the list: keep P1 (by name), rename by id, drop P3, add P4
        p2 = prio["options"][1]["id"]
        body = {"options": [{"name": "p1"}, {"id": p2, "name": "P2 media"}, {"name": "P4"}]}
        res = api_key_client.patch(v1(project, f"module-properties/{prio['id']}/"), body, format="json")
        assert res.status_code == 200, res.content
        assert [(o["name"], o["id"] == p2) for o in res.json()["options"]] == [
            ("P1", False),
            ("P2 media", True),
            ("P4", False),
        ]
        assert res.json()["options"][0]["id"] == p1  # value on E01 kept
        assert api_key_client.get(val(e01, prio)).json()["value"] == p1
        assert api_key_client.delete(v1(project, f"module-properties/{prio['id']}/")).status_code == 204
        assert prio["id"] not in api_key_client.get(v1(project, "module-property-values/")).json()[str(e01.id)]

    @pytest.mark.parametrize(
        "body",
        [
            {"display_name": "Notes", "property_type": "RELATION", "relation_type": "RICH_TEXT"},
            {"display_name": "", "property_type": "DECIMAL"},
        ],
    )
    def test_rejected_definitions(self, api_key_client, project, body):
        assert api_key_client.post(v1(project, "module-properties/"), body, format="json").status_code == 400

    def test_module_relation_only_on_modules(self, api_key_client, project):
        body = {"display_name": "Mod", "property_type": "RELATION", "relation_type": "MODULE"}
        assert api_key_client.post(v1(project, "work-item-properties/"), body, format="json").status_code == 400

    def test_members_set_values_but_only_admins_define(self, api_client, api_key_client, project, modules, workspace):
        prop = create(api_key_client, project, {"display_name": "Puntos", "property_type": "DECIMAL"})
        member = User.objects.create(email="mm@example.com", username="mm")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        project.project_projectmember.create(member=member, role=15, is_active=True, workspace=workspace)
        api_client.force_authenticate(user=member)
        url = v1(project, f"modules/{modules[0].id}/module-properties/{prop['id']}/values/")
        assert api_client.post(url, {"value": 1}, format="json").status_code == 201
        body = {"display_name": "x", "property_type": "DECIMAL"}
        assert api_client.post(v1(project, "module-properties/"), body, format="json").status_code == 403

    def test_computed_progress(self, api_key_client, project, modules, create_user):
        e01 = modules[0]
        done = State.objects.create(name="Done", project=project, workspace=project.workspace, group="completed")
        est = Estimate.objects.create(name="Pts", type="points", project=project, workspace=project.workspace)
        pt = {
            n: EstimatePoint.objects.create(
                estimate=est, key=n, value=str(n), project=project, workspace=project.workspace
            )
            for n in (3, 5)
        }

        def item(name, state=None, points=None, parent=None):
            issue = Issue.objects.create(
                name=name,
                project=project,
                workspace=project.workspace,
                created_by=create_user,
                state=state or State.objects.get(project=project, default=True),
                estimate_point=pt.get(points),
                parent=parent,
            )
            ModuleIssue.objects.create(module=e01, issue=issue, project=project, workspace=project.workspace)
            return issue

        story = item("story 1", done, 5)
        item("story 2", None, 3)
        item("task of story 1", done, 3, parent=story)  # counted with its story, not on its own

        out = api_key_client.get(v1(project, f"modules/{e01.id}/module-property-values/")).json()
        assert out["values"] == {}
        assert out["computed"] == {
            "work_items": 2,
            "work_items_done": 1,
            "work_items_cancelled": 0,
            "points_total": 8.0,
            "points_done": 5.0,
            "progress": 50,
        }

    def test_web_routes(self, session_client, project, modules):
        url = f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/oces/module-properties/"
        assert session_client.get(url).status_code == 200


def test_entity_managers(db, workspace):
    WorkItemProperty.all_objects.create(
        workspace=workspace, name="m", display_name="M", property_type="DECIMAL", entity="MODULE"
    )
    assert WorkItemProperty.objects.count() == 0 and WorkItemProperty.modules.count() == 1
