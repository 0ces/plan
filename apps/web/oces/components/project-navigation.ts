/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
import { EUserPermissions } from "@plane/constants";
import { EpicIcon } from "@plane/propel/icons";
import { Timer } from "lucide-react";
import { useProject } from "@/hooks/store/use-project";
import type { TNavigationItem } from "@/components/workspace/sidebar/project-navigation";
import { useWorkItemTypes } from "../store/use-work-item-types";

type TItems = (workspaceSlug: string, projectId: string) => TNavigationItem[];

/** Adds "Epics" (when the project has an epic type) and "Timesheet" (when time tracking is on) to a project's sidebar. */
export function useOcesProjectNavigation(workspaceSlug: string, projectId: string, upstream?: TItems): TItems {
  const store = useWorkItemTypes(workspaceSlug, projectId);
  const hasEpics = store.isEnabled(projectId) && !!store.getEpicType(projectId);
  const hasTime = !!useProject().getProjectById(projectId)?.is_time_tracking_enabled;
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
      {
        i18n_key: "Timesheet", // no translation key: t() shows it as is
        key: "timesheet",
        name: "Timesheet",
        href: `/${slug}/projects/${pid}/timesheet`,
        icon: Timer,
        access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        shouldRender: hasTime,
        sortOrder: 99,
      },
    ],
    [upstream, hasEpics, hasTime]
  );
}
