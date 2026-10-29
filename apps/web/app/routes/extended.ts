/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

// OCES: fork routes, merged into upstream's layouts by file path (docs/fork/UPSTREAM_EDITS.md)
const WS = "./(all)/[workspaceSlug]";
const PROJECT = `${WS}/(projects)/projects/(detail)/[projectId]`;
const PROJECT_SETTINGS = `${WS}/(settings)/settings/projects/[projectId]`;

export const extendedRoutes: RouteConfigEntry[] = [
  layout("./(all)/layout.tsx", [
    layout(`${WS}/layout.tsx`, [
      layout(`${WS}/(projects)/layout.tsx`, [
        layout(`${PROJECT}/layout.tsx`, [
          layout(`${PROJECT}/(oces)/epics/layout.tsx`, [
            route(":workspaceSlug/projects/:projectId/epics", `${PROJECT}/(oces)/epics/page.tsx`),
          ]),
        ]),
      ]),
      layout(`${WS}/(settings)/layout.tsx`, [
        layout(`${WS}/(settings)/settings/projects/layout.tsx`, [
          layout(`${PROJECT_SETTINGS}/layout.tsx`, [
            route(
              ":workspaceSlug/settings/projects/:projectId/work-item-types",
              `${PROJECT_SETTINGS}/(oces)/work-item-types/page.tsx`
            ),
          ]),
        ]),
      ]),
    ]),
  ]),
];
