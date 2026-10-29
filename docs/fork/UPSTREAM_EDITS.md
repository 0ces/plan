# Edits to upstream files

Every change to a file that came from upstream Plane is listed here, and each
edit carries an `OCES:` comment at the spot. `scripts/oces/check-upstream-edits.sh`
(CI) fails when a changed upstream file is missing from this list, or a listed
file lost its marker. Keep edits to one-liners: includes, aliases, hook calls.

Files we own entirely (not listed): `apps/api/plane/oces/`, `apps/web/oces/`,
`packages/types/src/oces/`, `docs/fork/`, `scripts/oces/`, `.github/workflows/oces-*`.

| File | Why |
|---|---|
| `apps/api/plane/settings/common.py` | add `plane.oces` to INSTALLED_APPS |
| `apps/api/plane/urls.py` | mount `plane.oces.urls.v1` / `.app` before upstream routes |
| `apps/web/tsconfig.json` | `@oces/*` path alias |
| `apps/api/plane/api/serializers/issue.py` | v1 work item `type_id` must belong to the project |
