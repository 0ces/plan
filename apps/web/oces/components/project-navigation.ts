/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
import { EUserPermissions } from "@plane/constants";
import { EpicIcon } from "@plane/propel/icons";
import type { TNavigationItem } from "@/components/workspace/sidebar/project-navigation";
import { useWorkItemTypes } from "../store/use-work-item-types";

type TItems = (workspaceSlug: string, projectId: string) => TNavigationItem[];

/** Adds an "Epics" entry to a project's sidebar when the project has an epic type. */
export function useOcesProjectNavigation(workspaceSlug: string, projectId: string, upstream?: TItems): TItems {
  const store = useWorkItemTypes(workspaceSlug, projectId);
  const hasEpics = store.isEnabled(projectId) && !!store.getEpicType(projectId);
  return useCallback(
    (slug: string, pid: string) => [
      ...(upstream ? upstream(slug, pid) : []),
      {
        i18n_key: "sidebar.epics",
        key: "epics",
        name: "Epics",
        href: `/${slug}/projects/${pid}/epics`,
        icon: EpicIcon,
        access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER, EUserPermissions.GUEST],
        shouldRender: hasEpics,
        sortOrder: 1.5,
      },
    ],
    [upstream, hasEpics]
  );
}
