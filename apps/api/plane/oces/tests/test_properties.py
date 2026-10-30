# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Issue, IssueActivity, ProjectMember, User, WorkspaceMember
from plane.oces.models import WorkItemPropertyValue
from plane.oces.pql import PQLError, parse_pql
from plane.oces.work_item_types import enable_project_types, project_types

from .test_work_item_types import make_project

TEXT = {"display_name": "Client", "property_type": "TEXT", "settings": {"display_format": "single-line"}}
OPTION = {
    "display_name": "Size",
    "property_type": "OPTION",
    "options": [{"name": "S"}, {"name": "M", "is_default": True}, {"name": "L", "color": "#ff0000"}],
}


@pytest.fixture
def project(db, workspace, create_user):
    project = make_project(workspace, create_user, "PR")
    enable_project_types(project)
    return project


@pytest.fixture
def task(project):
    return project_types(project.id).get(name="Task")


def v1(project, path=""):
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def type_url(project, issue_type, path=""):
    return v1(project, f"work-item-types/{issue_type.id}/work-item-properties/{path}")


def new_item(project, user, name="x", **kw):
    return Issue.objects.create(name=name, project=project, workspace=project.workspace, created_by=user, **kw)


def create(client, project, issue_type, body):
    res = client.post(type_url(project, issue_type), body, format="json")
    assert res.status_code == 201, res.content
    return res.json()


def value_url(project, issue, prop):
    return v1(project, f"work-items/{issue.id}/work-item-properties/{prop['id']}/values/")


@pytest.mark.contract
class TestDefinitions:
    def test_type_scoped_create_and_lists_are_plain_arrays(self, api_key_client, project, task):
        prop = create(api_key_client, project, task, TEXT)
        assert prop["name"] == "client" and prop["issue_type"] == str(task.id) and prop["options"] == []
        for url in (type_url(project, task), v1(project, "work-item-properties/")):
            body = api_key_client.get(url).json()
            assert isinstance(body, list) and [p["id"] for p in body] == [prop["id"]]
        ws = api_key_client.get(f"/api/v1/workspaces/{project.workspace.slug}/work-item-properties/").json()
        assert [p["id"] for p in ws] == [prop["id"]]
        bug = project_types(project.id).get(name="Bug")
        assert api_key_client.get(type_url(project, bug)).json() == []

    def test_inline_options_and_option_crud(self, api_key_client, project, task):
        prop = create(api_key_client, project, task, OPTION)
        assert [o["name"] for o in prop["options"]] == ["S", "M", "L"]
        assert prop["options"][2]["logo_props"]["color"] == "#ff0000"
        url = v1(project, f"work-item-properties/{prop['id']}/options/")
        made = api_key_client.post(url, {"name": "XL", "is_default": True}, format="json").json()
        names = [(o["name"], o["is_default"]) for o in api_key_client.get(url).json()]
        assert names == [("S", False), ("M", False), ("L", False), ("XL", True)]
        assert api_key_client.post(url, {"name": "xl"}, format="json").status_code == 400
        assert api_key_client.patch(f"{url}{made['id']}/", {"name": "XXL"}, format="json").json()["name"] == "XXL"
        assert api_key_client.delete(f"{url}{made['id']}/").status_code == 204

    @pytest.mark.parametrize(
        "body, key",
        [
            ({"display_name": "F", "property_type": "FORMULA"}, "property_type"),
            ({"display_name": "T", "property_type": "TEXT"}, "settings"),
            ({"display_name": "D", "property_type": "DATETIME", "settings": {"display_format": "x"}}, "settings"),
            ({"display_name": "R", "property_type": "RELATION"}, "relation_type"),
            ({"display_name": "R", "property_type": "RELATION", "relation_type": "RELEASE"}, "relation_type"),
            ({"display_name": "B", "property_type": "BOOLEAN", "is_multi": True}, "is_multi"),
            ({"property_type": "BOOLEAN"}, "display_name"),
        ],
    )
    def test_bad_definitions(self, api_key_client, project, task, body, key):
        res = api_key_client.post(type_url(project, task), body, format="json")
        assert res.status_code == 400 and key in res.json()

    def test_duplicate_name_update_and_delete(self, api_key_client, project, task):
        prop = create(api_key_client, project, task, TEXT)
        assert api_key_client.post(type_url(project, task), TEXT, format="json").status_code == 400
        res = api_key_client.patch(type_url(project, task, f"{prop['id']}/"), {"is_required": True}, format="json")
        assert res.json()["is_required"] is True and res.json()["settings"] == {"display_format": "single-line"}
        assert api_key_client.delete(v1(project, f"work-item-properties/{prop['id']}/")).status_code == 204
        assert api_key_client.get(type_url(project, task)).json() == []

    def test_attach_and_detach(self, api_key_client, project, task):
        flat = api_key_client.post(v1(project, "work-item-properties/"), TEXT, format="json").json()
        assert flat["issue_type"] is None
        links = v1(project, f"work-item-types/{task.id}/properties/")
        res = api_key_client.post(links, {"properties": [flat["id"]]}, format="json")
        assert res.status_code == 201 and res.json() == {"properties": [flat["id"]]}
        assert [p["id"] for p in api_key_client.get(type_url(project, task)).json()] == [flat["id"]]
        assert api_key_client.delete(f"{links}{flat['id']}/").status_code == 204
        assert api_key_client.get(type_url(project, task)).json() == []
        assert api_key_client.get(v1(project, f"work-item-properties/{flat['id']}/")).status_code == 200

    def test_members_cannot_define(self, api_client, project, task, workspace):
        member = User.objects.create(email="m@example.com", username="m")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        ProjectMember.objects.create(project=project, member=member, role=15, is_active=True)
        api_client.force_authenticate(user=member)
        assert api_client.get(type_url(project, task)).status_code == 200
        assert api_client.post(type_url(project, task), TEXT, format="json").status_code == 403


@pytest.mark.contract
class TestValues:
    def test_text_value_lifecycle_and_activity(self, api_key_client, project, task, create_user):
        prop = create(api_key_client, project, task, TEXT)
        item = new_item(project, create_user)
        url = value_url(project, item, prop)
        assert api_key_client.get(url).status_code == 404
        assert api_key_client.patch(url, {"value": "a"}, format="json").status_code == 404
        res = api_key_client.post(url, {"value": "Acme"}, format="json")
        assert res.status_code == 201
        body = res.json()
        assert body["value"] == "Acme" and body["property_id"] == prop["id"] and body["issue_id"] == str(item.id)
        assert api_key_client.patch(url, {"value": "Globex"}, format="json").json()["value"] == "Globex"
        assert api_key_client.delete(url).status_code == 204
        assert api_key_client.get(url).status_code == 404
        log = IssueActivity.objects.filter(issue=item, field="oces_property").order_by("created_at")
        assert [(a.old_value, a.new_value) for a in log] == [(None, "Acme"), ("Acme", "Globex"), ("Globex", None)]
        assert log[0].comment == "Client"

    @pytest.mark.parametrize(
        "body, good, bad",
        [
            ({"display_name": "N", "property_type": "DECIMAL"}, (4.5, 4.5), "4.5"),
            ({"display_name": "B", "property_type": "BOOLEAN"}, (False, False), "false"),
            (
                {"display_name": "D", "property_type": "DATETIME", "settings": {"display_format": "MMM dd, yyyy"}},
                ("2026-10-30", "2026-10-30"),
                "30/10/2026",
            ),
            ({"display_name": "U", "property_type": "URL"}, ("https://oces.dev", "https://oces.dev"), "nope"),
            ({"display_name": "E", "property_type": "EMAIL"}, ("a@b.co", "a@b.co"), "a@"),
        ],
    )
    def test_typed_values(self, api_key_client, project, task, create_user, body, good, bad):
        prop = create(api_key_client, project, task, body)
        url = value_url(project, new_item(project, create_user), prop)
        assert api_key_client.post(url, {"value": bad}, format="json").status_code == 400
        assert api_key_client.post(url, {"value": good[0]}, format="json").json()["value"] == good[1]

    def test_multi_option_returns_list(self, api_key_client, project, task, create_user):
        prop = create(api_key_client, project, task, {**OPTION, "is_multi": True})
        s, m, _ = (o["id"] for o in prop["options"])
        url = value_url(project, new_item(project, create_user), prop)
        res = api_key_client.post(url, {"value": [s, m]}, format="json").json()
        assert isinstance(res, list) and [v["value"] for v in res] == [s, m]
        assert [v["value"] for v in api_key_client.post(url, {"value": m}, format="json").json()] == [m]
        other = create(api_key_client, project, task, {**OPTION, "display_name": "Other"})
        assert api_key_client.post(url, {"value": other["options"][0]["id"]}, format="json").status_code == 400

    def test_single_option_rejects_list(self, api_key_client, project, task, create_user):
        prop = create(api_key_client, project, task, OPTION)
        url = value_url(project, new_item(project, create_user), prop)
        assert api_key_client.post(url, {"value": [prop["options"][0]["id"]]}, format="json").status_code == 400

    def test_rich_text_needs_an_object(self, api_key_client, project, task, create_user):
        prop = create(
            api_key_client,
            project,
            task,
            {"display_name": "Notes", "property_type": "RELATION", "relation_type": "RICH_TEXT"},
        )
        url = value_url(project, new_item(project, create_user), prop)
        res = api_key_client.post(url, {"value": "<p>x</p>"}, format="json")
        assert res.status_code == 400 and "Rich text value must be an object" in res.content.decode()
        body = api_key_client.post(
            url, {"value": {"description_html": "<p>Hi <script>x</script></p>"}}, format="json"
        ).json()
        assert body["value_detail"]["description_stripped"].startswith("Hi")
        assert "script" not in body["value_detail"]["description_html"]

    def test_user_relation(self, api_key_client, project, task, create_user):
        prop = create(
            api_key_client,
            project,
            task,
            {"display_name": "Owner", "property_type": "RELATION", "relation_type": "USER"},
        )
        url = value_url(project, new_item(project, create_user), prop)
        stranger = User.objects.create(email="s@example.com", username="s")
        assert api_key_client.post(url, {"value": str(stranger.id)}, format="json").status_code == 400
        assert api_key_client.post(url, {"value": str(create_user.id)}, format="json").json()["value"] == str(
            create_user.id
        )

    def test_property_of_another_type_is_refused(self, api_key_client, project, task, create_user):
        prop = create(api_key_client, project, task, TEXT)
        bug = project_types(project.id).get(name="Bug")
        url = value_url(project, new_item(project, create_user, type=bug), prop)
        assert api_key_client.post(url, {"value": "x"}, format="json").status_code == 400

    def test_defaults_on_create(self, api_key_client, project, task, create_user, django_capture_on_commit_callbacks):
        size = create(api_key_client, project, task, OPTION)
        create(
            api_key_client, project, task, {"display_name": "Pts", "property_type": "DECIMAL", "default_value": ["3"]}
        )
        with django_capture_on_commit_callbacks(execute=True):
            res = api_key_client.post(v1(project, "work-items/"), {"name": "new"}, format="json")
        rows = WorkItemPropertyValue.objects.filter(issue_id=res.json()["id"])
        got = {
            r.property.display_name: (r.value_option and r.value_option.name) or float(r.value_decimal) for r in rows
        }
        assert got == {"Size": "M", "Pts": 3.0} and size

    def test_limited_guest_cannot_read_others_values(
        self, api_client, api_key_client, project, task, create_user, workspace
    ):
        prop = create(api_key_client, project, task, TEXT)
        item = new_item(project, create_user)
        api_key_client.post(value_url(project, item, prop), {"value": "secret"}, format="json")
        guest = User.objects.create(email="g@example.com", username="g")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
        api_client.force_authenticate(user=guest)
        assert api_client.get(value_url(project, item, prop)).status_code in (403, 404)

    def test_internal_all_values(self, session_client, api_key_client, project, task, create_user):
        text = create(api_key_client, project, task, TEXT)
        size = create(api_key_client, project, task, {**OPTION, "is_multi": True})
        item = new_item(project, create_user)
        api_key_client.post(value_url(project, item, text), {"value": "Acme"}, format="json")
        api_key_client.post(value_url(project, item, size), {"value": [size["options"][0]["id"]]}, format="json")
        url = (
            f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/oces/work-items/{item.id}/property-values/"
        )
        assert session_client.get(url).json() == {text["id"]: "Acme", size["id"]: [size["options"][0]["id"]]}


@pytest.mark.contract
class TestPQL:
    @pytest.fixture
    def data(self, api_key_client, project, task, create_user):
        props = {
            "size": create(api_key_client, project, task, OPTION),
            "pts": create(api_key_client, project, task, {"display_name": "Pts", "property_type": "DECIMAL"}),
            "ok": create(api_key_client, project, task, {"display_name": "Ok", "property_type": "BOOLEAN"}),
            "client": create(api_key_client, project, task, TEXT),
            "mail": create(api_key_client, project, task, {"display_name": "Mail", "property_type": "EMAIL"}),
        }
        s, m, _ = (o["id"] for o in props["size"]["options"])
        WorkItemPropertyValue.objects.all().delete(soft=False)  # drop defaults; set values explicitly
        for name, size, pts, ok, client in (
            ("A", s, 1, True, "Acme"),
            ("B", m, 5, False, "Globex"),
            ("C", None, None, None, None),
        ):
            item = new_item(project, create_user, name)
            WorkItemPropertyValue.objects.filter(issue=item).delete(soft=False)
            for key, value in (("size", size), ("pts", pts), ("ok", ok), ("client", client)):
                if value is not None:
                    api_key_client.post(value_url(project, item, props[key]), {"value": value}, format="json")
        return props, s, m

    def names(self, project, user, pql):
        q = parse_pql(pql, user, project.workspace.slug, project.id)
        return sorted(Issue.issue_objects.filter(project=project).filter(q).values_list("name", flat=True))

    def test_filters(self, project, create_user, data):
        props, s, m = data
        cf = lambda k: f'cf["{props[k]["id"]}"]'  # noqa: E731
        cases = {
            f'{cf("size")} = "{s}"': ["A"],
            f'{cf("size")} IN ("{s}", "{m}")': ["A", "B"],
            f'{cf("size")} NOT IN ("{s}")': ["B", "C"],
            f"{cf('size')} IS NULL": ["C"],
            f"{cf('size')} IS NOT NULL": ["A", "B"],
            f"{cf('pts')} >= 5": ["B"],
            f"{cf('pts')} BETWEEN 0 AND 2": ["A"],
            f"{cf('ok')} = true": ["A"],
            f'{cf("client")} ~ "glo"': ["B"],
            f'{cf("client")} != "Acme"': ["B", "C"],
        }
        for pql, expected in cases.items():
            assert self.names(project, create_user, pql) == expected, pql

    @pytest.mark.parametrize(
        "pql",
        [
            'cf["00000000-0000-0000-0000-000000000000"] = "x"',
            "cf[{pts}] = 1",
            'cf["{pts}"] = "5"',
            'cf["{ok}"] = "true"',
            'cf["{mail}"] = "a@b.co"',
            'cf["{client}"] IN ("a")',
            'cf["{pts}"] ~ "1"',
        ],
    )
    def test_errors(self, project, create_user, data, pql):
        props = data[0]
        with pytest.raises(PQLError):
            parse_pql(
                pql.format(**{k: v["id"] for k, v in props.items()}), create_user, project.workspace.slug, project.id
            )

    def test_endpoint(self, api_key_client, project, data):
        props, s, _ = data
        res = api_key_client.get(v1(project, "work-items/"), {"pql": f'cf["{props["size"]["id"]}"] = "{s}"'})
        assert [r["name"] for r in res.json()["results"]] == ["A"]
