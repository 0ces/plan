Plane CE v1.4.3 + oces fork, release 7.

## New

- **Time tracking**: log time on work items. Turn it on per project in Project settings → Features → Time tracking.
  - Work item side panel and peek: a "Time logged" row with the total. Click it to log time (`1h 30m`, `45m`, `1.5h` or `1:30`), pick the day and add a note, and to edit or delete entries.
  - Work item lists show a small total on each row that has time logged.
  - **Timesheet** page in the project sidebar: hours per person per day for a week, each person expandable into the work items they worked on.
  - Members and admins log time; guests don't see it. You change your own entries; project admins can change anyone's.
- **Public API** at Plane's official paths (`/api/v1/workspaces/{slug}/projects/{project_id}/`), so the `work_log` tool in plane-mcp-server works without changes:
  - `work-items/{work_item_id}/worklogs/` (GET list, POST `{duration, description?, logged_at?}`; duration in minutes, 1–1440)
  - `work-items/{work_item_id}/worklogs/{id}/` (GET, PATCH, DELETE)
  - `worklogs/summary/` (total minutes per work item)
  - `worklogs/?from=YYYY-MM-DD&to=YYYY-MM-DD&logged_by=` (entries in a date range, up to a year)
- The Epics page and sidebar entry now hide when the project's epic type is turned off.

## Migrations

- `oces.0006_work_logs`: one new table (`oces_work_logs`). Nothing else changes.

## Deploy

Set `OCES_RELEASE=oces-v1.4.3-7`, back up, then:
`docker compose pull web admin api worker beat-worker migrator live && docker compose up -d --no-deps migrator web admin api worker beat-worker live`
