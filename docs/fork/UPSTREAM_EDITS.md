# Edits to upstream files

Every change to a file that came from upstream Plane is listed here, and each
edit carries an `OCES:` comment at the spot. `scripts/oces/check-upstream-edits.sh`
(CI) fails when a changed upstream file is missing from this list, or a listed
file lost its marker. Keep edits to one-liners: includes, aliases, hook calls.

Files we own entirely (not listed): `apps/api/plane/oces/`, `apps/web/oces/`, `apps/live/src/oces/`, `apps/live/tests/oces/`,
`packages/types/src/oces/`, route folders named `(oces)` under `apps/web/app/`, `docs/fork/`, `scripts/oces/`, `.github/workflows/oces-*`.

| File                                                                | Why                                                                                     |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `apps/api/plane/settings/common.py`                                 | add `plane.oces` to INSTALLED_APPS; live-updates middleware at the end of MIDDLEWARE    |
| `apps/api/plane/urls.py`                                            | mount `plane.oces.urls.v1` / `.app` before upstream routes                              |
| `apps/web/tsconfig.json`                                            | `@oces/*` path alias                                                                    |
| `apps/api/plane/api/serializers/issue.py`                           | v1 work item `type_id` must belong to the project                                       |
| `apps/api/plane/app/serializers/issue.py`                           | internal work item `type_id` field + project check; `type_id` in IssueSerializer fields |
| `apps/api/plane/app/views/issue/base.py`                            | `type_id` in work item list/create field lists                                          |
| `apps/api/plane/utils/grouper.py`                                   | `type_id` in grouped list fields                                                        |
| `apps/web/app/routes/extended.ts`                                   | fork routes: project Epics page, Work item types settings                               |
| `apps/web/core/components/workspace/sidebar/project-navigation.tsx` | Epics sidebar entry                                                                     |
| `apps/web/core/components/issues/issue-detail/issue-identifier.tsx` | type icon before identifiers                                                            |
| `apps/web/core/components/issues/issue-type-switcher.tsx`           | type picker + epic progress on detail page                                              |
| `apps/web/core/components/issues/issue-modal/form.tsx`              | type picker in the create/edit modal                                                    |
| `apps/web/core/components/issues/issue-modal/provider.tsx`          | default type when the project changes                                                   |
| `apps/web/core/components/settings/project/sidebar/item-icon.tsx`   | icon for the settings entry                                                             |
| `packages/constants/src/settings/project.ts`                        | Work item types settings entry                                                          |
| `packages/types/src/settings.ts`                                    | settings tab key                                                                        |
| `apps/live/src/controllers/index.ts`                                | register the live-updates websocket (`/live/oces/events`)                               |
| `apps/web/app/(all)/[workspaceSlug]/layout.tsx`                     | mount `OcesLiveEvents` once per workspace                                               |
