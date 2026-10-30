/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { LiveEvents } from "./live-events";

/** Keeps the workspace's screens up to date without refreshing. Mounted once in the workspace layout. */
export function OcesLiveEvents({ workspaceSlug }: { workspaceSlug: string }) {
  useEffect(() => {
    if (!workspaceSlug || typeof window === "undefined") return;
    const live = new LiveEvents(workspaceSlug);
    live.start();
    return () => live.stop();
  }, [workspaceSlug]);
  return null;
}
