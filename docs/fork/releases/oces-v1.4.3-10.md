Plane CE v1.4.3 + oces fork, release 10.

## Fixed

- **Live updates no longer blank the work item list.** When a change needed the whole list reloaded (bulk edits, state/label/cycle/module changes, saved views, archives, reconnecting), the list emptied while the request ran, so the board looked like the page was refreshing. It now swaps old for new in one step. Single work item changes were already updated in place.

## Not covered

- After loading more items by scrolling, such a reload still returns to the first page, same as upstream.

## Migrations

None.

## Deploy

Set `OCES_RELEASE=oces-v1.4.3-10`, back up, then:
`docker compose pull web admin api worker beat-worker migrator live && docker compose up -d --no-deps migrator web admin api worker beat-worker live`
