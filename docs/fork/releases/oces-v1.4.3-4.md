Plane CE v1.4.3 + oces fork, release 4.

## New

- **Initiatives** (workspace feature `initiatives`, off until an admin turns it on): CRUD, links to projects, epics and work items, progress roll-up, labels (API only). Sidebar entry, list and detail pages.
- **Pages public API** at the official paths, so the Plane MCP `page` tool works. Project and workspace pages: list, retrieve, create (with `parent_id` nesting), update, archive/restore, delete. Pages can also be linked to work items (`work-items/<id>/pages/`). HTML sent to the API is converted by the live server into the editor's document format, so pages open and can be edited normally in the web editor. Collections are not available (400).
- **Version check**: `GET /api/v1/oces/version/` (any API key) reports the running release, the latest fork release and the latest Plane release. Workspace admins and god-mode show a dismissible notice when either is newer. `/api/instances/` now carries `oces_version` and `oces_commit`.
- **Own admin image** `plan-admin` (needed for the god-mode notice).

## Migrations

- `oces.0003_initiatives`, `oces.0004_pages_and_versions`. Both only add tables.

## New environment variables (all optional)

- `OCES_VERSION_CHECK=0` turns off the GitHub check (air-gapped installs). Default on.
- `OCES_GITHUB_TOKEN`: read-only token, only needed while github.com/0ces/plan is private.
- `OCES_LIVE_INTERNAL_URL`: where the API reaches the live server. Default `LIVE_BASE_URL` + `LIVE_BASE_PATH`, else `http://live:3000/live/`.
- The API now uses `LIVE_SERVER_SECRET_KEY` (already in the standard compose `app-env`) to call the live server.
- `OCES_VERSION` / `OCES_COMMIT` are baked into `plan-backend` at build time. Do not set them by hand.

## Deploy

Add `image: registry3.oces.dev/plan-admin:${OCES_RELEASE}` for `admin` in `docker-compose.override.yml`, set `OCES_RELEASE=oces-v1.4.3-4`, then:
`docker compose up -d --no-deps migrator web admin api worker beat-worker live`
