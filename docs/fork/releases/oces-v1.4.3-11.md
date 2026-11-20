Plane CE v1.4.3 + oces fork, release 11.

## Security

- **nginx 1.31.9 in `plan-web` and `plan-admin`.** Rebuilt on `nginx:1.31-alpine`, which now ships 1.31.9 and fixes the nginx 2026 advisories (HTTP/2 flow control and use-after-free, HTTP/3 use-after-free, resolver use-after-free, TLS 1.3 request body loop). Release 10 had nginx 1.31.8. Behind Traefik these were not reachable, so this is hygiene, not an emergency.

## Changed

Nothing else. Same code as release 10; `plan-backend` and `plan-live` are rebuilt only to keep one tag across the images.

## Migrations

None.

## Deploy

Set `OCES_RELEASE=oces-v1.4.3-11`, then:
`docker compose pull web admin api worker beat-worker migrator live && docker compose up -d --no-deps migrator web admin api worker beat-worker live`
