/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TEpicProgress } from "../types";

/** Done share of an epic's children; cancelled items count as done-for-progress like Plane's cycles. */
export function epicPercent(p: TEpicProgress) {
  return p.total_issues ? Math.round(((p.completed_issues + p.cancelled_issues) / p.total_issues) * 100) : 0;
}

export function EpicProgressBar({ progress }: { progress: TEpicProgress }) {
  const percent = epicPercent(progress);
  return (
    <div className="flex items-center gap-2" title={`${progress.completed_issues} of ${progress.total_issues} done`}>
      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-layer-3">
        <div className="h-full rounded-full bg-success-primary" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-20 text-12 text-tertiary">
        {progress.total_issues ? `${percent}% · ${progress.completed_issues}/${progress.total_issues}` : "No items"}
      </span>
    </div>
  );
}
