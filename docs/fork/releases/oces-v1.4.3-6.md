Plane CE v1.4.3 + oces fork, release 6.

## New

- **Module properties**: custom fields on modules, defined per project (Project settings → Module properties) and edited in the module side panel. Filled-in values show as chips in the module list. Kinds: text, paragraph, number, checkbox, date, dropdown, URL, email, member, and **Module** (links to other modules in the project, e.g. "Depends on"). Built for "module = epic, work items = stories, sub-items = tasks".
- **Computed progress** per module, from its top-level work items (a sub-item whose parent is in the same module is not counted again): work items, done, cancelled, points total/done (points estimates only), % progress. Read-only, through the API.
- **Public API**, shaped like the work item property endpoints (`/api/v1/workspaces/{slug}/projects/{project_id}/`):
  - `module-properties/` and `module-properties/{id}/` (definitions; PATCH with `options` replaces the dropdown options)
  - `module-properties/{id}/options/[{option_id}/]`
  - `modules/{module_id}/module-properties/{id}/values/` (GET, POST set, DELETE clear)
  - `modules/{module_id}/module-property-values/` (all values + `computed`)
  - `module-property-values/` (all values of every module in the project)
- **MCP**: the fork github.com/0ces/plane-mcp-server (tag `oces-v0.3.5-1`) adds a `module_property` tool for all of the above.
- Module and cycle descriptions show in full (release 5).

## Migrations

- `oces.0005_module_properties`: adds a column (`entity`, default work item) to the property table and a new value table. Nothing else changes.

## Deploy

Set `OCES_RELEASE=oces-v1.4.3-6`, back up, then:
`docker compose pull web admin api worker beat-worker migrator live && docker compose up -d --no-deps migrator web admin api worker beat-worker live`

MCP config (both instances):
`uvx --from git+https://github.com/0ces/plane-mcp-server@oces-v0.3.5-1 plane-mcp-server stdio`
