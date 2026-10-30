#!/usr/bin/env bash
# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# Fails when an upstream file changed since the upstream base tag is not listed
# in docs/fork/UPSTREAM_EDITS.md, or a listed file has no OCES: marker.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
base="$(cat docs/fork/UPSTREAM_BASE)"
list=docs/fork/UPSTREAM_EDITS.md
owned='^(apps/api/plane/oces/|apps/web/oces/|apps/live/src/oces/|apps/live/tests/oces/|apps/web/app/.*/\(oces\)/|packages/types/src/oces/|docs/fork/|scripts/oces/|\.github/workflows/oces-)'
fail=0
# Upstream files we changed (A = files we added outside owned dirs also count).
while IFS= read -r f; do
  [[ "$f" =~ $owned ]] && continue
  if ! grep -qF "\`$f\`" "$list"; then echo "not listed in $list: $f"; fail=1; fi
done < <(git diff --name-only "$base")
# Every listed file still carries a marker.
while IFS= read -r f; do
  [[ -f "$f" ]] || { echo "listed but missing: $f"; fail=1; continue; }
  grep -q "OCES:" "$f" || { echo "no OCES: marker in $f"; fail=1; }
done < <(grep -oE '^\| `[^`]+`' "$list" | sed -E 's/^\| `([^`]+)`/\1/')
[[ $fail -eq 0 ]] && echo "upstream edits OK"
exit $fail
