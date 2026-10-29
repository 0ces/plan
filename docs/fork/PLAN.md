# Fork plan: our own "paid" features on Plane CE

Status: **draft, waiting for approval. Nothing is built yet.**
Base: `makeplane/plane` tag `v1.4.3` (commit `37a15d992`), the version running at plane.oces.dev.
Repo: `0ces/plan` (private). Remotes: `origin` = 0ces/plan, `upstream` = makeplane/plane.
Companion: [`api-contract.md`](api-contract.md) lists the official public API paths and fields we must match.

## Ground rules

- **Our own code only.** Never copy code from Plane's closed paid editions. Never patch their commercial images or license checks. The public API contract (paths, fields, enums) comes from the public docs and the open-source `plane-sdk` / `plane-mcp-server`. We implement it ourselves.
- **AGPL-3.0.** Every new file gets the SPDX AGPL header (upstream CI runs `addlicense -check`). If clients use the fork over the web, they must be offered the source of our changes. Sharing this private repo on request is enough.
- **Trademarks.** The name is fine for private use. If the fork is ever offered to others, rename it and replace the Plane name and logo.
- **MCP compatibility.** Our endpoints match the official `/api/v1/` paths and payloads, so the existing `plane-personal` MCP (plane-mcp-server 0.3.5) works against the fork unchanged.

## What CE v1.4.3 already gives us

| Area | Already in CE | Missing |
|---|---|---|
| Work item types / epics | `IssueType` model (`is_epic`, `level`, `logo_props`, `is_default`), `ProjectIssueType`, `Issue.type` FK, `Project.is_issue_type_enabled`. Web: `EIssueServiceType.EPICS`, `epicDetail` store, empty `CreateUpdateEpicModal` and epic empty state, `is_epic` branches in the sidebar and nav. | Every endpoint (internal and v1). The web app already calls `/api/workspaces/:slug/projects/:id/epics/...`, which returns 404 today. |
| Custom properties | nothing | everything |
| Initiatives | the slug `initiatives` is reserved | everything |
| Workflows / approvals | no-op web stubs: `useWorkFlowFDragNDrop` (always allows) and `StateOption` (`filterAvailableStateIds` is ignored). Real automations (auto-archive, auto-close). | rules, enforcement, approvals |
| Client portal | Guest role (5) with per-project membership. `Project.guest_view_all_features`: when off, a guest sees only the work items they created. Guests can comment. Full Intake (internal, v1 and a public intake via `DeployBoard`). The space app publishes project boards. | Customers, a client-safe view, approvals by the client, and a security audit of what guests can see at workspace level |
| Releases | nothing | everything |
| Dashboards | analytics endpoints (`advance-analytics*`, `analytic-view`, `project-stats`) and the web analytics tabs (`core/components/analytics/tabs.tsx`). The old Dashboard/Widget models were deprecated in migration 0090. | custom dashboards, widgets, burn-up history |
| MCP plumbing | — | `GET/PATCH {ws}/features/` and `{ws}/projects/{p}/features/` (the MCP checks these before using any paid tool). PQL: `?pql=` returns **400** "not supported on this edition" (`api/views/issue.py:317`), so MCP `workitem list` with filters, including listing an epic's children, fails today. |

Gating to know about: `plane/license` is the instance-admin app, not license enforcement. There are no license-key checks to touch. The upsell UI (`components/license/modal/`, `workspace/billing/`, `edition-badge.tsx`, `isPro` badges in `project/settings/features-list.tsx`) is plain UI. We hide it where we implement the feature. A telemetry beat task exists (`license/bgtasks/telemetry_metrics.py`). Turning it off is optional (step F0).

## Staying mergeable with upstream

1. **Backend in its own Django app**: `apps/api/plane/oces/` with its own `models/`, `migrations/`, `api/` (v1 views), `app/` (internal views), `bgtasks/` and `tests/`. We never add migrations to upstream's `db` app, so upstream's migration chain (latest `0122`) stays conflict-free. Our models point to upstream ones by FK. The only upstream table we write to is `issue_types` (the model already exists), plus `issues.type_id`.
2. **Routing without editing upstream views**: `plane/urls.py` mounts `plane.oces.urls` *before* upstream's `api/v1/` and `api/` includes. Django resolves the first match, so our view for an existing path (for example the work item list with PQL) overrides upstream's without touching its file.
3. **Upstream edits are small and marked.** The only allowed edits are one-line includes or hook calls, each tagged `# OCES:` / `// OCES:`, and listed in `docs/fork/UPSTREAM_EDITS.md`. A CI step fails when an `OCES:` marker in an upstream file is missing from that list. Expected edits: `settings/common.py` (INSTALLED_APPS), `plane/urls.py`, the work-item state-change paths (workflow hook), and on the web side the existing stubs (epic modal, workflow hooks, `StateOption`), `routes/extended.ts`, nav and sidebar entries, and the analytics tabs.
4. **Frontend code in its own folders**: `apps/web/oces/` (pages, components, MobX stores, services) behind a `@oces/*` alias added to `apps/web/tsconfig.json` and `vite.config.ts`. Shared types go in `packages/types/src/oces/`. New routes register through `app/routes/extended.ts`, which upstream ships as an empty extension point.
5. **Upgrading**: on each upstream release, branch `upgrade/v1.x.y`, run `git merge v1.x.y`, resolve conflicts (only the marked lines should clash), run our tests plus upstream's API tests, then stage on a local compose before deploying.
6. **Tests**: pytest for every model, endpoint and permission in `plane/oces/tests/`. Add an MCP smoke test: a script that runs the plane-mcp-server tools against a local stack (type, property, value, initiative, release, PQL list).

## Features: design, effort, order

Effort is in focused dev-days with Claude writing the code and Edwar reviewing and testing. It covers backend, API, UI and tests for a solid v1, not every paid-edition option.

### F0. Foundation — 4 days
- `plane.oces` Django app, the `@oces` web alias, and the `UPSTREAM_EDITS.md` check.
- **Feature flags**: models `OcesWorkspaceFeature` and `OcesProjectFeature` holding the MCP keys (`initiatives`, `work_item_types`, `releases`, `customers`, `epics`, `workflows`, …). Endpoints `GET/PATCH /api/v1/workspaces/{ws}/features/` and `.../projects/{p}/features/`, plus internal equivalents for the web settings UI. Features we have not built return `false`.
- CI: GitHub Actions builds and pushes images (see Deploy). Copyright-header check on new files.
- Optional: an env switch to turn off telemetry.

### F1. PQL subset on work item lists — 5 days
Override `projects/{p}/work-items/`, `work-items/`, `archived-work-items/` and `work-items/count/` to accept `?pql=`. Implement a small parser that turns PQL into a Django `Q`, for the operators the MCP reference uses most: field comparisons (state, state group, priority, assignee, label, type, cycle, module, dates), `AND`/`OR`/`NOT`, `IN`, `childOf()`, and later custom properties. Unknown syntax returns 400 `{"pql": "..."}`, which the MCP shows with its reference. Without PQL, the MCP's epic workflow (list an epic's children) cannot work.

### 1. Work item types (incl. epics) — 8 days
- **Models**: reuse upstream `IssueType` and `ProjectIssueType`. We only add a per-type field schema (step 2) and type ordering.
- **API (v1, matching the contract)**: project-scoped `projects/{p}/work-item-types/[{id}/]`. Workspace-scoped `work-item-types/[{id}/]`, plus `import-work-item-types/` and `work-item-types/{id}/properties/`. Lists are plain arrays. Work item create/update accept `type_id`. Start with **project mode** (`work_item_types` workspace feature = false). The MCP supports it fully, and it is simpler.
- **Internal API**: `epics/` endpoints the web app already calls (list, detail, create, update, delete, sub-issues, progress), plus type CRUD for settings.
- **Behaviour**: enabling types in a project creates the default types Task, Bug, Feature and Epic (Epic with `is_epic=true`, `level=1`). Existing items get `type = default` (Task). Epics are hidden from normal lists, matching upstream's archive filter. Epic progress = children counted by state group (and estimate points when estimates are on).
- **UI**: project settings → Work item types (name, icon and colour via `logo_props`, description, active, default). Type picker in the create modal and the sidebar. Type icon next to the identifier (the `issueTypeId` props already exist). Epics page per project with a progress bar and child list. Fill in the existing `CreateUpdateEpicModal`.

### 2. Custom properties — 12 days
- **Models**:
  - `IssueProperty`: workspace; project (nullable); issue_type (nullable); name, display_name, description; `property_type`; `relation_type`; `settings` JSON; `is_required`, `is_multi`, `is_active`; `default_value`; sort_order; external_*.
  - `IssuePropertyOption`: property, name, sort_order, is_default, logo_props.
  - `IssuePropertyValue`: issue, property, plus typed columns `value_text`, `value_decimal`, `value_boolean`, `value_datetime`, `value_option` FK and `value_uuid`. Multi-values are one row per value. Indexed by (property, value) for filters.
- **Types in v1**: TEXT (single-line, multi-line), DECIMAL (number), URL, EMAIL, DATETIME (date), OPTION (dropdown, single or multi), BOOLEAN. Not yet: FORMULA, CASCADING and FILE return 400 "not supported". RELATION (USER / ISSUE / RELEASE) comes after Releases (≈3 more days).
- **API**: properties and options at all three scopes from the contract, and values at `projects/{p}/work-items/{wi}/work-item-properties/{prop}/values/` (GET, POST, PATCH, DELETE; `{"value": ...}`; multi returns a list). Validation (required fields, URL/email format, `settings.display_format`) happens on the server, and the error texts the MCP relies on are kept.
- **Also**: changes are written to work item activity so they show in history. Properties count as PQL fields (`F1` extension). Properties are shown and edited in list, spreadsheet and detail views. Filtering by property in the web UI comes after the detail sidebar.
- **UI**: a property editor inside each type's settings, with drag ordering. Work item detail sidebar renders and edits values. Required properties are enforced in the create modal.

### 3. Initiatives — 7 days
- **Models**: `Initiative` (workspace, name, description_html, lead, start_date, end_date, `state` DRAFT/PLANNED/ACTIVE/COMPLETED/CLOSED, logo_props). Link tables `InitiativeProject`, `InitiativeEpic`, `InitiativeWorkItem`. `InitiativeLabel` and its link table.
- **API**: `initiatives/[{id}/]` with `/projects/`, `/epics/`, `/work-items/` and `/labels/` sub-paths, plus `initiatives/labels/`, as in the contract. The workspace feature `initiatives` becomes true.
- **Progress rollup**: for linked projects, all work items; for linked epics, their children; counted by state group, de-duplicated. Computed in SQL on request, with no denormalised counters yet.
- **UI**: a workspace sidebar entry "Initiatives" with a list (state, lead, dates, progress) and a detail page (description, linked projects and epics with their own progress, updates through comments).

### 4. Releases — 7 days
- **Models**: `Release` (workspace, name, `version`, `status` unreleased/released/cancelled, start_date, release_date, description_html = release notes, lead). `ReleaseWorkItem`. `ReleaseLabel` and its link table. `ReleaseTag`. `ReleaseComment`. `ReleaseLink`.
- **API**: `releases/[{id}/]` with `changelog/`, `work-items/` (`{"work_item_ids": [...]}`), `labels/`, `comments/` and `links/`, plus `releases/labels/` and `releases/tags/`, as in the contract.
- **Changelog**: generated from the release's work items in the completed state group, grouped by work item type (Feature / Bug / Task), as markdown and HTML. It can be pasted into the notes and edited.
- **UI**: a workspace "Releases" list and detail page with the notes editor (the existing rich-text editor), work items added by search, a warning for unfinished items, and a "Mark released" button that sets the date.

### 5. Workflows & approvals — 12 days (biggest upstream touch)
- **Models**:
  - `Workflow`: project, is_active.
  - `WorkflowTransition`: workflow, `from_state` (null = any), `to_state`, `allowed_roles`, M2M `allowed_members`, `requires_approval`, M2M `approvers`, M2M `auto_assignees`, `assign_mode` (add or replace).
  - `WorkflowApproval`: issue, transition, requested_by, `status` pending/approved/rejected, decided_by, decided_at, comment.
- **Enforcement on the server, in one function** `oces.workflow.check_and_apply(issue, new_state, user)`. It is called from every place a state changes: the internal issue PATCH, bulk update (kanban and spreadsheet), the v1 PATCH, intake accept, issue create with a state, and archive/restore if relevant. Each call is a one-line `# OCES:` hook. A `pre_save` guard on `Issue.state_id` acts as a safety net, so a path we missed fails loudly in tests instead of silently skipping the rule.
  - Disallowed move → 403 with the reason.
  - Move that needs approval → the state does not change. A pending approval is created, approvers get a notification (the existing notification task) and an activity entry.
  - Approve → the state moves.
  - Auto-assign runs after any successful move.
- **API**: `POST projects/{p}/work-items/{wi}/workflow-approval/` with `{"type": "approve"|"reject"}`, matching the SDK. Internal endpoints for workflow CRUD and pending approvals ("my approvals").
- **UI**: project settings → Workflow as a from/to matrix of states with rules per cell. The state dropdown only offers allowed states (fill in the `StateOption` `filterAvailableStateIds` stub). Kanban drag is blocked or prompts (fill in the `useWorkFlowFDragNDrop` stub). An approval banner on the work item with Approve / Reject. A "Pending approvals" inbox filter.

### 6. Dashboards — 10 days
- **Models**: `Dashboard` (workspace, owner, name, is_shared). `DashboardWidget` (dashboard, `chart_type` bar/line/pie/number/table, `config` JSON {metric, group_by, x_axis, filters: projects, types, labels, assignees, property values, date range}, layout position). `WorkItemDailySnapshot` (date, project, state_group, type, count, points), filled by a nightly Celery beat task and backfilled once from work item activity.
- **Widgets in v1**:
  - **Workload**: open work items or points per assignee, split by state group.
  - **Burn-up**: scope vs completed over time, from the snapshots, for a project, epic, initiative or release.
  - **By client**: grouped by project or by Customer (step 7), or by a custom property such as "Client".
  - **Generic**: count or points grouped by state, priority, type, label or property.
  - Aggregation reuses the queryset helpers from upstream's `advance-analytics-charts`.
- **API**: internal only, since there is no public dashboards API and the MCP has no dashboard tool. Endpoints: `workspaces/{ws}/oces-dashboards/...`. Upstream's dead web `DashboardService` URLs are left alone.
- **UI**: a new "Dashboards" tab in workspace analytics (`analytics/tabs.tsx`). Charts use `recharts`, already a dependency via `@plane/propel`. Widgets sit in a fixed two-column grid ordered by drag. A free-form grid layout is skipped for now.

### 7. Client portal / guests — 14 days (last, security-sensitive)
- **Approach**: a client is a **Guest** member of only their own project(s), linked to a **Customer** record. We reuse the main web app in a guest-restricted mode instead of building a second portal. That means less code and one auth system. The space app stays for public read-only boards and intake forms.
- **Customers (MCP compat)**: `Customer` (name, email, website, logo, `stage`, `contract_status`, …), `CustomerProperty` and values, `CustomerRequest` (name, description_html, link, work_item_ids), customer↔work item links, and customer↔project and customer↔guest-user links. API as in the contract (`customers/...`). The workspace feature `customers` becomes true.
- **What a client can do**: see only their projects; per project, choose "all work items" (`guest_view_all_features`) or "only items shared with the client" (a new `client_visible` flag per work item, set by members); comment; submit requests (intake); approve or reject (they can be workflow approvers, step 5; approving a release or a deliverable uses the same mechanism).
- **Security work, the main cost**:
  - Audit every workspace-level internal endpoint a guest can reach: members list, search, notifications, mentions, pages, analytics, views, cycles and modules, attachments, activity, and the user-profile endpoints. Write a permission test matrix (role × endpoint) that runs in CI.
  - Hide internal comments: add a comment `access` value, internal or client, that defaults to internal for members.
  - Make sure dashboards, initiatives and releases are never readable by guests.
  - Rate-limit and audit-log guest actions.
  - Before launch, a run of `/security-review` and the security-auditor agent.
- **UI**: a slim navigation for guests (their projects, "My requests", "Pending approvals"), an internal/client toggle on the comment box, and Customer pages for members.

### Total and build order

| # | Item | Days |
|---|---|---|
| F0 | Foundation, feature flags, CI and images | 4 |
| F1 | PQL subset | 5 |
| 1 | Work item types and epics | 8 |
| 2 | Custom properties | 12 |
| 3 | Initiatives | 7 |
| 4 | Releases (+ RELATION properties, 3) | 7 + 3 |
| 5 | Workflows & approvals | 12 |
| 6 | Dashboards | 10 |
| 7 | Client portal + Customers + security audit | 14 |
| | **Total** | **≈ 82 dev-days** |

Order: F0 → 1 → F1 → 2 → 3 → 4 → 5 → 6 → 7. F1 comes after types because `childOf` and `type =` are its main use. Each step ends deployed to plane.oces.dev and checked with the MCP before the next starts.

Out of scope: time tracking (billcalc covers it; a Plane→billcalc link comes later), milestones, templates, collections, teamspaces, workspace-owned type catalogues, FORMULA / CASCADING / FILE properties, and SSO.

## Deploy on svr3

Current setup (`/root/plane`, see `NOTES.md` there): upstream `docker-compose.yml` (untouched), `docker-compose.override.yml` (Traefik labels on `proxy`) and `.env` with `APP_RELEASE=v1.4.3`. Images are pulled from Docker Hub `makeplane/*`.

1. **Build**: `.github/workflows/oces-ci.yml` (done in F0) runs on tags `oces-v1.4.3-N` (upstream version + our build number). It uses `docker/build-push-action` for linux/amd64 with the upstream Dockerfiles and default build args, so the URLs stay relative, same as the official images. It pushes:
   - `registry3.oces.dev/plan-backend:<tag>` (`apps/api/Dockerfile.api`, used by api, worker, beat-worker and migrator)
   - `registry3.oces.dev/plan-web:<tag>` (`apps/web/Dockerfile.web`)
   - `registry3.oces.dev/plan-space:<tag>` (only once step 7 touches space)

   admin, live and proxy stay on upstream `makeplane/*` images until we change them.

   Registry login uses repo secrets `DOCKER_USERNAME` / `DOCKER_PASSWORD` and variable `DOCKER_REGISTRY`, the same pattern as culpacafe's `deploy.yml`. Edwar sets the secrets.
2. **Switch on svr3**: add `image:` lines to `docker-compose.override.yml` only:
   ```yaml
   services:
     web:          { image: registry3.oces.dev/plan-web:${OCES_RELEASE} }
     api:          { image: registry3.oces.dev/plan-backend:${OCES_RELEASE} }
     worker:       { image: registry3.oces.dev/plan-backend:${OCES_RELEASE} }
     beat-worker:  { image: registry3.oces.dev/plan-backend:${OCES_RELEASE} }
     migrator:     { image: registry3.oces.dev/plan-backend:${OCES_RELEASE} }
   ```
   Add `OCES_RELEASE=oces-v1.4.3-N` to `.env`. Keep `APP_RELEASE` equal to the upstream base so admin, live and proxy match. Service names match the running containers (plane-web-1, plane-api-1, plane-worker-1, plane-beat-worker-1, plane-migrator-1).
3. **Deploy**: back up first (pg_dump + uploads, as in NOTES.md). Then `docker compose pull && docker compose up -d` in `/root/plane`. The migrator applies our `oces` migrations. Only Plane containers restart; Traefik and other apps are untouched. svr3 must be logged in to registry3, as it already is for other apps (check before the first deploy).
4. **Rollback**: set the override image tags back, or remove the `image:` lines to return to stock CE. Our tables are additive and live in our own app, so stock CE runs fine with them present. Data in them just goes unused.
5. **Upstream upgrade**: merge the new tag (see "Staying mergeable"), tag `oces-v1.x.y-1`, then on svr3 update `docker-compose.yml` per NOTES.md, `APP_RELEASE` and `OCES_RELEASE` together.
6. Update `/root/plane/NOTES.md` with the fork section when it first deploys.

## Open questions for Edwar

1. Repo and folder are named `plan` (not `plane`). Is that intended? It is fine either way, and it could become the product name later.
2. Is "client" a **Customer** record (paid-Plane style, works with the MCP `customer` tools) or just a project label? This plan assumes Customer.
3. For the client portal, is the main web app restricted for guests enough, or do you want a separate branded portal URL (e.g. `clientes.oces.dev`)? A separate portal adds ≈5 days.
4. May the fork turn off upstream telemetry?
