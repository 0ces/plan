# Plane public API contract for paid features (as used by plane-mcp-server)

Sources read (read-only, nothing executed):

- PyPI `plane-sdk` 0.3.2 (wheel) — `plane/api/**` (v1 resources), `plane/models/**`.
- PyPI `plane-mcp-server` 0.3.5 (wheel) — `plane_mcp/tools/**`, `plane_mcp/toolkit/**`.
- Context7 `/makeplane/developer-docs` (API reference pages).
- Extracted to a local scratch dir during research (not kept).

Legend: `{ws}` = workspace slug, `{p}` = project_id. **[MCP]** = actually called by plane-mcp-server 0.3.5; other rows are SDK-only (implement later / optional). **(?)** = uncertain.

---

## i. Auth, base path, conventions

| Item                        | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Base                        | `{PLANE_BASE_URL}/api/v1` (SDK `Configuration`: `base_path.rstrip("/") + "/api/v1"`). MCP env: `PLANE_INTERNAL_BASE_URL` or `PLANE_BASE_URL` (default `https://api.plane.so`), `PLANE_API_KEY`, `PLANE_WORKSPACE_SLUG`.                                                                                                                                                                                                                                                                                                                          |
| Auth                        | `X-Api-Key: <key>` (API key) **or** `Authorization: Bearer <token>` (OAuth). Never both. `Content-Type: application/json`.                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Resource roots              | `/api/v1/workspaces/{ws}/...` and `/api/v1/workspaces/{ws}/projects/{p}/...`; `/api/v1/users/me/`.                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Trailing slash              | SDK `_build_url` **always appends `/`** (`.../work-items/`). Fork must accept the trailing-slash form (Django `APPEND_SLASH` won't help for POST/PATCH).                                                                                                                                                                                                                                                                                                                                                                                         |
| JSON writes                 | Bodies are `model_dump(exclude_none=True)` — only set fields are sent. Partial update = PATCH.                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Success codes               | 204 or empty body → None. JSON parsed only if `content-type` contains `application/json`.                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Pagination envelope         | `{grouped_by, sub_grouped_by, total_count, next_cursor, prev_cursor, next_page_results, prev_page_results, count, total_pages, total_results, extra_stats, results:[...]}`. Cursor format `"<per_page>:<page>:<is_prev>"` e.g. `20:1:0`. Query: `cursor`, `per_page` (1–100), `expand`, `fields`, `order_by`, `external_id`, `external_source`. **SDK requires all of `total_count,next_cursor,prev_cursor,next_page_results,prev_page_results,count,total_pages,total_results` (non-null strings/ints) — pydantic validation fails otherwise.** |
| Error shapes MCP interprets | `400 {"code":"workspace_managed"}` / `{"code":"workspace_not_managed"}` / `{"code":"governance_migration_in_progress"}`; `402` or 400 whose text contains "upgrade your plan" → "not available on plan"; 400 body with key `pql` (or mentioning pql/filter) → shown as invalid PQL; 404 → "absent".                                                                                                                                                                                                                                              |

### Feature flags (MCP probes these before paid features!)

| Method              | Path                          | Body/Response fields                                                                                                                          |
| ------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| GET/PATCH **[MCP]** | `{ws}/features/`              | `project_grouping, initiatives, teams, customers, wiki, pi, work_item_types, releases, states_owned_by_workspace` (bools; last is read-only). |
| GET/PATCH **[MCP]** | `{ws}/projects/{p}/features/` | `epics, modules, cycles, views, pages, intakes, work_item_types, workflows, parallel_cycles, project_updates`                                 |

- `initiative` tool calls `GET {ws}/features/` first and refuses unless `initiatives == true`.
- `workitem_type resolve`: reads `{ws}/features/.work_item_types`; true ⇒ workspace-owned catalogue path (create at workspace + import). Else reads project features; if `work_item_types` false it PATCHes `{"work_item_types": true}` then creates a project type.
- (?) CE v1.4.3 likely has no `/api/v1/.../features/` endpoints — the fork must add them (at least GET, and PATCH for project `work_item_types`).

---

## a. Work item types

Types exist at **both** scopes. Mode is decided by workspace feature `work_item_types` (true = workspace owns the catalogue and projects import types; false = per-project types).

| Method                         | Path                                                                                                                                                         | Notes                                                                                                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET **[MCP]**                  | `{ws}/projects/{p}/work-item-types/`                                                                                                                         | **Plain JSON array** (SDK does `[WorkItemType(...) for item in response]`), even though MCP passes cursor/per_page. Lists types joined to the project in either mode. |
| POST **[MCP]**                 | `{ws}/projects/{p}/work-item-types/`                                                                                                                         | Create project type. 400 `{"code":"workspace_managed"}` (or body containing key `work_item_types`) when workspace owns types.                                         |
| GET / PATCH / DELETE **[MCP]** | `{ws}/projects/{p}/work-item-types/{type_id}/`                                                                                                               |                                                                                                                                                                       |
| POST **[MCP]**                 | `{ws}/projects/{p}/import-work-item-types/`                                                                                                                  | Body `{"work_item_types": ["<ws type uuid>", ...]}`; response ignored.                                                                                                |
| GET **[MCP]**                  | `{ws}/work-item-types/`                                                                                                                                      | Plain array, no pagination.                                                                                                                                           |
| POST **[MCP]**                 | `{ws}/work-item-types/`                                                                                                                                      |                                                                                                                                                                       |
| GET / PATCH / DELETE **[MCP]** | `{ws}/work-item-types/{type_id}/`                                                                                                                            |                                                                                                                                                                       |
| GET **[MCP]**                  | `{ws}/work-item-types/{type_id}/properties/`                                                                                                                 | Returns **flat list of property UUID strings**.                                                                                                                       |
| POST **[MCP]**                 | `{ws}/work-item-types/{type_id}/properties/`                                                                                                                 | Body `{"properties": ["<prop uuid>", ...]}` (link).                                                                                                                   |
| DELETE **[MCP]**               | `{ws}/work-item-types/{type_id}/properties/{property_id}/`                                                                                                   | Unlink only.                                                                                                                                                          |
| SDK-only                       | `{ws}/work-item-types/{type_id}/governance/` (GET/PATCH), `.../governance/preview/` (POST), `.../governance/pins/` (GET/POST), `.../pins/{pin_id}/` (DELETE) | Workflow governance; skip.                                                                                                                                            |

**WorkItemType (response)**: `id, name, description, logo_props (object, e.g. {}), is_epic (bool), is_default (bool), is_active (bool), level (int; docs show 0 normal, 1 in an epic example), project_ids [uuid], workspace, project (docs), external_source, external_id, created_at, updated_at, created_by, updated_by, deleted_at`. Model is `extra="allow"`; only `name` is required.

**Create/Update body**: `name` (req on create), `description, logo_props, is_epic, is_active, level, project_ids, external_source, external_id`. MCP only sends `name, description, project_ids, is_active, external_*`.

**Epics**: MCP has _no_ epic tool. MCP instructions: "an epic is a work item whose type is named 'Epic'" — `workitem_type resolve name="Epic"` → `type_id`, then `workitem create type_id=...`, list with `pql='type = "<uuid>"'`, children via `pql='childOf("PROJ-12")'`. So `is_epic` is just a flag on the type; MCP never reads it. Initiatives fallback likewise uses a type named "Initiative".
SDK-only epic endpoints (not used by MCP): `GET/POST {ws}/projects/{p}/epics/`, `GET/PATCH/DELETE .../epics/{epic_id}/`, `GET/POST .../epics/{epic_id}/issues/` (body `{"work_item_ids":[...]}`). CreateEpic fields: `name, description_html, state_id, parent_id, assignee_ids, label_ids, priority, start_date, target_date, estimate_point, external_*`.

---

## b. Work item properties, options, values

Three scopes chosen by MCP from the ids supplied: (project_id + type_id) = type-scoped; project_id only = project-flat; neither = workspace catalogue.

| Method                     | Path                                                                                     | MCP                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| GET/POST                   | `{ws}/projects/{p}/work-item-types/{type_id}/work-item-properties/`                      | [MCP]                                                                          |
| GET/PATCH/DELETE           | `{ws}/projects/{p}/work-item-types/{type_id}/work-item-properties/{property_id}/`        | [MCP]                                                                          |
| GET/POST                   | `{ws}/projects/{p}/work-item-properties/`                                                | [MCP] (project-flat)                                                           |
| GET/PATCH/DELETE           | `{ws}/projects/{p}/work-item-properties/{property_id}/`                                  | [MCP]                                                                          |
| POST                       | `{ws}/projects/{p}/work-item-types/{type_id}/properties/` (attach existing)              | [MCP] body `{"properties":["<prop uuid>",...]}`                                |
| DELETE                     | `{ws}/projects/{p}/work-item-types/{type_id}/properties/{property_id}/` (detach)         | [MCP]                                                                          |
| GET/POST                   | `{ws}/work-item-properties/`                                                             | [MCP] workspace catalogue; "no ids lists every workspace property in one call" |
| GET/PATCH/DELETE           | `{ws}/work-item-properties/{property_id}/`                                               | [MCP]                                                                          |
| GET/POST                   | `{ws}/projects/{p}/work-item-properties/{property_id}/options/`                          | [MCP]                                                                          |
| GET/PATCH/DELETE           | `{ws}/projects/{p}/work-item-properties/{property_id}/options/{option_id}/`              | [MCP]                                                                          |
| GET/POST, GET/PATCH/DELETE | `{ws}/work-item-properties/{property_id}/options/[ {option_id}/ ]`                       | [MCP] workspace-scope options                                                  |
| GET/POST/PATCH/DELETE      | `{ws}/projects/{p}/work-items/{work_item_id}/work-item-properties/{property_id}/values/` | [MCP]                                                                          |

All property and option **list responses are plain JSON arrays** (no pagination envelope) at every scope (verified in SDK).

**property_type enum**: `TEXT, DATETIME, DECIMAL, BOOLEAN, OPTION, RELATION, URL, EMAIL, FILE, FORMULA, CASCADING`.
**relation_type enum** (required when `RELATION`): `ISSUE, USER, RELEASE, RICH_TEXT`. (Rich text = `RELATION` + `RICH_TEXT`.)
**settings**: required for TEXT → `{"display_format": "single-line"|"multi-line"|"readonly"}`; required for DATETIME → `{"display_format": "MMM dd, yyyy"|"dd/MM/yyyy"|"MM/dd/yyyy"|"yyyy/MM/dd"}`; others `null`. MCP defaults to `single-line` / `MMM dd, yyyy`.

**WorkItemProperty (response)**: `id, name (derived slug), display_name (required), description, logo_props, sort_order, property_type, relation_type, is_required, default_value [str], settings, is_active, is_multi, validation_rules, external_source, external_id, workspace, project, issue_type, options [Option], created_*/updated_*/deleted_at`.
**Create body**: `display_name, property_type` (req), `description, relation_type, is_required, default_value, settings, is_active, is_multi, validation_rules, external_*, options:[{name, description, is_active, is_default, external_*, parent}]` (inline options on create). MCP sets `is_active=true` for workspace creates.
**Option**: `id, name, sort_order, description, logo_props, is_active, is_default, external_*, workspace, project, property, parent (for CASCADING)`. Create/Update: `name, description, is_active, is_default, external_*, parent`.

**Values** (per work item × property):

- POST = upsert (single) / replace-all (multi). PATCH = partial update (404 if none). GET (404 if not set). DELETE removes all values.
- Request: `{"value": <v>, "external_id"?, "external_source"?}` where v = string (TEXT/URL/EMAIL/FILE), `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` (DATETIME), number (DECIMAL), bool (BOOLEAN), UUID (OPTION/RELATION single), `[UUID]` or UUID (is_multi), `{"description_html": "<p>..</p>"}` (RICH_TEXT — a bare string must 400 with text "Rich text value must be an object"; MCP retries on that exact message).
- Response: single object or **list for is_multi**: `{id, property_id, issue_id, value, value_type, value_detail: {id, description_html, description_stripped}|null, external_id, external_source, created_at, updated_at}`.
- Storage model hint (WorkItemPropertyValue): `value_text, value_boolean, value_decimal, value_datetime, value_uuid, value_option, issue, property`.

---

## c. Initiatives (workspace-scoped)

| Method                     | Path                                      | Body / response                                                                                                             |
| -------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------- |
| GET **[MCP]**              | `{ws}/initiatives/`                       | Response `{results:[Initiative]}` — SDK model needs only `results` (MCP says "does not paginate"; full envelope also fine). |
| POST **[MCP]**             | `{ws}/initiatives/`                       | `name` (req), `description_html, start_date, end_date, logo_props, state, lead`                                             |
| GET/PATCH/DELETE **[MCP]** | `{ws}/initiatives/{initiative_id}/`       |                                                                                                                             |
| GET **[MCP]**              | `{ws}/initiatives/{id}/projects/`         | Paginated envelope of Project                                                                                               |
| POST **[MCP]**             | `{ws}/initiatives/{id}/projects/`         | `{"project_ids":[...]}` → array of Project                                                                                  |
| DELETE **[MCP]**           | `{ws}/initiatives/{id}/projects/`         | body `{"project_ids":[...]}` (DELETE with JSON body)                                                                        |
| GET **[MCP]**              | `{ws}/initiatives/{id}/work-items/`       | Paginated envelope of WorkItem                                                                                              |
| POST / DELETE **[MCP]**    | `{ws}/initiatives/{id}/work-items/`       | `{"work_item_ids":[...]}`; POST → array of WorkItem                                                                         |
| GET/POST/DELETE            | `{ws}/initiatives/{id}/epics/`            | `{"epic_ids":[...]}`; GET paginated Epic                                                                                    | SDK-only |
| GET/POST, GET/PATCH/DELETE | `{ws}/initiatives/labels/[ {label_id}/ ]` | Label: `id, name, description, color, sort_order, workspace`                                                                | SDK-only |
| GET/POST/DELETE            | `{ws}/initiatives/{id}/labels/`           | `{"label_ids":[...]}`                                                                                                       | SDK-only |

Routing note: `initiatives/labels/` must be routed before `initiatives/{uuid}/`.
**Initiative**: `id, name, description, description_html, description_stripped, description_binary, start_date, end_date, logo_props (dict, required in model → return `{}`), state, lead, workspace (required), created_at, updated_at, deleted_at`.
**state enum**: `DRAFT, PLANNED, ACTIVE, COMPLETED, CLOSED`.

---

## d. Releases (workspace-scoped)

| Method                               | Path                                            | Notes                                                                                                                                                                                                                                                   |
| ------------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET/POST **[MCP]**                   | `{ws}/releases/`                                | GET paginated                                                                                                                                                                                                                                           |
| GET/PATCH/DELETE **[MCP]**           | `{ws}/releases/{release_id}/`                   |                                                                                                                                                                                                                                                         |
| GET/PATCH **[MCP]**                  | `{ws}/releases/{release_id}/changelog/`         | Created empty with the release (GET always returns one). PATCH `{description_html, description_json (ProseMirror doc)}`. Response `{id, changelog, created_*, updated_*, workspace, release}`                                                           |
| GET/POST/DELETE **[MCP]**            | `{ws}/releases/{release_id}/work-items/`        | POST/DELETE body `{"work_item_ids":[...]}`, response ignored. GET paginated `{id, name, project_id}`                                                                                                                                                    |
| GET/POST/DELETE **[MCP]**            | `{ws}/releases/{release_id}/labels/`            | attach/detach labels: `{"label_ids":[...]}`; POST → array of ReleaseLabel                                                                                                                                                                               |
| GET/POST, GET/PATCH/DELETE **[MCP]** | `{ws}/releases/labels/[ {label_id}/ ]`          | ReleaseLabel `{id, name, color, sort_order, workspace}`; create `name` req, `color, sort_order(int)`                                                                                                                                                    |
| GET/POST, GET/PATCH/DELETE **[MCP]** | `{ws}/releases/tags/[ {tag_id}/ ]`              | ReleaseTag `{id, version, description, commit_hash, git_tag, name, color, sort_order, workspace, created_at, updated_at}`; create `version` req + `description, commit_hash, git_tag, name, color`; update `version, description, commit_hash, git_tag` |
| GET/POST, GET/PATCH/DELETE           | `{ws}/releases/{id}/comments/[ {comment_id}/ ]` | SDK-only. Create `{comment_html, parent}`; update `{comment_html, is_resolved}`                                                                                                                                                                         |
| GET/POST, GET/PATCH/DELETE           | `{ws}/releases/{id}/links/[ {link_id}/ ]`       | SDK-only. `{url, title, metadata}`                                                                                                                                                                                                                      |

Route `releases/labels/` and `releases/tags/` before `releases/{uuid}/`.
**Release**: `id, name, description, status, target_date, release_date, start_date, lead, tag, is_latest, is_prerelease, logo_props, external_*, created_*, updated_*, workspace`. Create body: `name` (req), `description_html, description_json, description, status, release_date, target_date, start_date, tag (uuid), lead (uuid), is_prerelease, logo_props, external_*`.
**status enum**: `unreleased` (default), `released`, `cancelled`. UI "Target date" = `release_date`.

---

## e. Customers (workspace-scoped; relevant to client portal)

| Method                               | Path                                                                | Notes                                                                                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET/POST **[MCP]**                   | `{ws}/customers/`                                                   | GET paginated; query `query` (search), `cursor`, `per_page`                                                                                                |
| GET/PATCH/DELETE **[MCP]**           | `{ws}/customers/{customer_id}/`                                     |                                                                                                                                                            |
| DELETE                               | `{ws}/customers/?external_source=..&external_id=..`                 | delete by external id (SDK)                                                                                                                                |
| GET/POST, GET/PATCH/DELETE **[MCP]** | `{ws}/customer-properties/[ {property_id}/ ]`                       | GET paginated                                                                                                                                              |
| GET **[MCP]**                        | `{ws}/customers/{id}/property-values/`                              | Response `{"<property_id>": ["v", ...], ...}`                                                                                                              |
| POST                                 | `{ws}/customers/{id}/property-values/`                              | `{"customer_property_values": {"<prop_id>": ["v"]}}` upsert, response ignored                                                                              |
| GET **[MCP]**                        | `{ws}/customers/{id}/property-values/{property_id}/`                | same dict shape, SDK picks key                                                                                                                             |
| PATCH                                | `{ws}/customers/{id}/property-values/{property_id}/`                | `{"values": [...]}`                                                                                                                                        |
| GET/POST, GET/PATCH/DELETE **[MCP]** | `{ws}/customers/{id}/requests/[ {request_id}/ ]`                    | GET paginated; query `query`                                                                                                                               |
| GET **[MCP]**                        | `{ws}/customers/{id}/issues/`                                       | **Plain array** of `{id, name, state_id, priority, sequence_id, project_id, project_identifier, created_at, updated_at}`; optional `?customer_request_id=` |
| POST **[MCP]**                       | `{ws}/customers/{id}/issues/[?customer_request_id=]`                | `{"work_item_ids":[...]}` → `{message, linked_work_items:[{id,name,sequence_id,project_id,project_identifier}]}`                                           |
| DELETE **[MCP]**                     | `{ws}/customers/{id}/issues/{work_item_id}/[?customer_request_id=]` |                                                                                                                                                            |

**Customer**: `id, name (req), description, description_html, description_stripped, description_binary, email, website_url, logo_props, logo_url, logo_asset, domain, employees (int), stage, contract_status, revenue (str), customer_request_count, archived_at, external_*, created_*, updated_*, workspace, deleted_at`.

- `stage`: `lead, sales_qualified_lead, contract_negotiation, closed_won, closed_lost` (from MCP tool; (?) server may accept free strings).
- `contract_status`: `active, pre_contract, signed, inactive`.
  **CustomerProperty**: like work item property but `property_type ∈ TEXT, DATETIME, DECIMAL, BOOLEAN, OPTION, RELATION, URL, EMAIL, FILE` (no FORMULA/CASCADING), `relation_type ∈ ISSUE, USER`; fields `name (req on create), display_name (req, unique in workspace), description, logo_props, sort_order, is_required, default_value, settings, is_active, is_multi, validation_rules, external_*, options:[{name, description, is_default}]` (update options items may carry `id`).
  **CustomerRequest**: `id, name (req), description, description_html, link, work_item_ids [uuid], attachment_count, created_at`. Create/update: `name, description, description_html, link, work_item_ids`. (MCP: work_item_ids "never echoed back".)

---

## f. Other paid features (paths only)

**Milestones** (project) [MCP]: `GET/POST {ws}/projects/{p}/milestones/` (paginated), `GET/PATCH/DELETE .../milestones/{id}/`, `GET/POST/DELETE .../milestones/{id}/work-items/` (body `{"issues":[...]}`; GET paginated `{id, issue, milestone}`). Milestone: `id, title (req), target_date, external_*, created_at, updated_at`.

**Templates** [MCP: list/create/delete (+update in SDK)]:

- Workspace: `{ws}/workitems/templates/`, `{ws}/projects/templates/`, `{ws}/pages/templates/` (+ `{template_id}/` PATCH/DELETE). Fields `name, description, description_html, template_data, logo_props`.
- Project: `{ws}/projects/{p}/workitems/templates/`, `{ws}/projects/{p}/pages/templates/` (+ `{template_id}/`). Fields `name, short_description, template_data`; response adds `template_type, project, workspace`.

**Work logs** [MCP]: `GET/POST {ws}/projects/{p}/work-items/{wi}/worklogs/` (GET = **plain array**), `PATCH/DELETE .../worklogs/{id}/`; body `{description, duration (int, minutes (?)), created_by, updated_by}`; response `{id, description, duration, logged_by, project_id, workspace_id, created_*, updated_*}`. Project summary `GET {ws}/projects/{p}/total-worklogs/` [MCP].

**Collections** (wiki) [MCP]: `GET/POST {ws}/collections/` (GET plain array), `GET/PATCH/DELETE {ws}/collections/{id}/` (DELETE `?archive_pages=true|false`), `GET/POST {ws}/collections/{id}/members/`, `PATCH/DELETE .../members/{member_id}/`, `GET/POST {ws}/collections/{id}/pages/` (POST `{page_ids, sort_orders?, placement?}`), `GET .../pages-search/`, `PATCH/DELETE .../pages/{page_collection_id}/`. access ints: collection 0/1, member 0/1/2.

**Custom relations / dependencies** [MCP]: `{ws}/work-item-relation-definitions/` (+`{id}/`), `{ws}/projects/{p}/work-items/{wi}/work-item-relations/` (+`{related_id}/`), `.../dependencies/` (+`{related_id}/`).

- **Fork status (oces-v1.4.3-9, `plane/oces/relation_views.py`)**: CE keeps every relation in one `IssueRelation` table, so these map onto it. Served: `dependencies/` GET + POST (`{relation_type, work_item_ids}`, the six directional types), `dependencies/{related_id}/` DELETE (directional types only), `work-item-relations/` GET (`relates_to`, `duplicate`), `work-item-relations/{related_id}/` DELETE (any type; it is the MCP's default `delete` route), SDK `relations/remove` POST `{related_issue}` (with or without the trailing slash), and `work-item-relation-definitions/` GET (always an empty page). Deletes work from either side, write the UI's `issue_relation.activity.deleted` activity, and return 404 when there is no relation. List rows are work items plus `relation_type`. Not served: `work-item-relations/` POST and definition create/update/delete, because CE has no custom definitions.

---

## g. Workflows / approvals / dashboards

- **Workflows & approvals DO exist in the SDK public API** (not used by MCP 0.3.5 — no workflow tool; only `projects/{p}/features.workflows` flag):
  - Project: `{ws}/projects/{p}/workflows/` (+`{id}/`, `{id}/activities/`, `{id}/states/` attach/`{state_id}/` update/detach/`transfer/`, `{id}/state-transitions/` (+`{transition_id}/`), transition hooks).
  - Workspace: `{ws}/workflows/` (+`{id}/usage/`, `activities/`, `states/…/mark-default/`, `state-transitions/`, hooks with `regenerate_secret`, `executions`).
  - Approval: `POST {ws}/projects/{p}/work-items/{wi}/workflow-approval/` body `{"type": "approve"|"reject"}` → `{state_id}`.
  - Transition: `{state_id, transition_state_id, type ("transition"|"approval" per plane-compose docs), member_ids (approvers), pre_rules, post_rules}`. Workflow: `{name, description, is_active, is_default, work_item_type_ids}`.
  - Per-type workflow pick: `{ws}/projects/{p}/work-item-types/{type_id}/workflow/` GET/PUT, `.../work-item-types/workflows/` GET.
- **Dashboards**: none in SDK v1 or docs (only a health probe). Confirmed absent. (SDK v2 namespace has `automations`, `webhooks` — not used by MCP.)

---

## h. PQL & work item create

- `workitem list` with `project_id` → `GET {ws}/projects/{p}/work-items/?pql=<expr>&order_by&per_page&cursor&expand&fields&external_id&external_source`. Without project_id → `GET {ws}/work-items/?pql=...` (workspace-wide). `list_archived` → `GET {ws}/projects/{p}/archived-work-items/?pql=...`. `count` → `GET {ws}/work-items/count/?pql=...&group_by&sub_group_by` (MCP ANDs `project = "<uuid>"` into pql). SDK also supports a `filters=` JSON query param (MCP doesn't send it).
- Response must be the full pagination envelope (MCP `envelope()` raises if fields missing).
- Invalid PQL → return **400 with key `pql`** (e.g. `{"pql": "message"}`) so MCP shows the fix-it reference.
- **Paid?** Not stated explicitly. The public "List all work items" doc page does not list `pql`, the developer docs say Community = Cloud Free tier, and MCP has no plan-gate on PQL. (?) Treat as not present in CE v1.4.3: **CE will silently ignore `pql` and return unfiltered results** — the fork must implement it. Fields to support (from MCP `pql_reference.py`): `priority, stateGroup, isDraft, isArchived, title ~, text ~, id = "WEB-11"/~ prefix, dueDate, startDate, createdAt, updatedAt, assignee, state, label, cycle, module, project, createdBy, type, milestone, mention, subscriber, teamspaceProject`, `cf["<prop uuid>"]` (=, IN, IS NULL), functions `currentUser(), openStates(), isOverdue(), activeCycle(), completedCycles(), upcomingCycles(), childOf("PROJ-12")`, operators `= != IN ~ AND OR NOT`. Full grammar in `plane_mcp/pql_reference.py` (377 lines) — read that when implementing.
- **Create**: `POST {ws}/projects/{p}/work-items/` body field is **`type_id`** (uuid). Model also has a legacy `type` field; MCP sends only `type_id`. Other fields MCP sends: `name, assignees[], labels[], point, description_html, priority (urgent|high|medium|low|none), start_date, target_date (explicit null allowed), sort_order, is_draft, external_source, external_id, parent, state, estimate_point`. Response WorkItem includes `type_id`.
- Also used: `GET {ws}/work-items/{PROJ}-{seq}/` (by identifier), `GET {ws}/work-items/search/`, archive `POST .../work-items/{id}/archive/`, unarchive `DELETE .../work-items/{id}/unarchive/`.

---

## Implementation priorities for the fork (MCP compatibility)

1. Feature-flag endpoints (`{ws}/features/`, `{ws}/projects/{p}/features/`) with the extra keys, else initiative/type tools break.
2. PQL on the 3 list endpoints + count, with 400 `{"pql": ...}`.
3. Type endpoints at both scopes + import; types list = plain array.
4. Property/option/value endpoints at 3 scopes; values multi → list.
5. Initiatives (+projects, +work-items), Releases (+labels/tags/changelog/work-items), Customers (+properties/values/requests/issues), Milestones, Templates, Work logs, Collections.
