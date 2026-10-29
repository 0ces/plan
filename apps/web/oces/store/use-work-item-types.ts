/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { workItemTypesStore } from "./work-item-types.store";

/** Returns the shared types store and makes sure the project's types are loaded. */
export function useWorkItemTypes(workspaceSlug?: string | null, projectId?: string | null) {
  useEffect(() => {
    if (workspaceSlug && projectId) void workItemTypesStore.fetch(workspaceSlug, projectId);
  }, [workspaceSlug, projectId]);
  return workItemTypesStore;
}
