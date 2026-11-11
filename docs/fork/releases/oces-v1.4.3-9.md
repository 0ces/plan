Plane CE v1.4.3 + oces fork, release 9.

## Fixed

- **Removing work item relations through the API / Plane MCP.** `workitem_relation delete` (MCP 0.3.x, plane-sdk 0.3.1) returned 404/405 because CE has no public delete. These routes now exist (API key, project admin or member; guests and other workspaces get 403):
  - `DELETE /api/v1/workspaces/{slug}/projects/{p}/work-items/{id}/work-item-relations/{related_id}/`: the MCP's default (`is_dependency=false`). Removes any relation type between the two items.
  - `DELETE .../work-items/{id}/dependencies/{related_id}/`: MCP with `is_dependency=true`. Removes only blocked_by/blocking, start_before/after and finish_before/after.
  - `POST .../work-items/{id}/relations/remove/` with body `{"related_issue": "<id>"}`: plane-sdk `work_items.relations.delete` (works with or without the trailing slash).
  - Works from either side of the relation, writes the same activity entries as the web app's "remove relation", and returns 404 when there is no relation.
  - One delete removes **every** relation between the two items that the route covers (all types on `work-item-relations/` and `relations/remove`, all directional types on `dependencies/`), not only one type. Archived work items can be listed and unlinked too.
- **`workitem_relation list` / `create` / `list_definitions` through the MCP**, which also failed on missing routes:
  - `GET|POST .../work-items/{id}/dependencies/`: the six directional types, with SDK body `{relation_type, work_item_ids}`.
  - `GET .../work-items/{id}/work-item-relations/`: relates_to and duplicate.
  - `GET /api/v1/workspaces/{slug}/work-item-relation-definitions/`: an empty list, since CE has no custom relation definitions.
  - List rows are now full work items (id, name, sequence_id, state…) plus `relation_type`.

## Not covered

- Creating relates_to/duplicate through the MCP: the MCP only creates those as "custom relations", which need definitions CE doesn't have. Use the web app or upstream `POST .../work-items/{id}/relations/` with `{relation_type, issues}`. Definition create/update/delete stay 404.

## Migrations

None.

## Deploy

Set `OCES_RELEASE=oces-v1.4.3-9`, back up, then:
`docker compose pull web admin api worker beat-worker migrator live && docker compose up -d --no-deps migrator web admin api worker beat-worker live`
