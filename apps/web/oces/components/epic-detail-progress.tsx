/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { WorkItemTypesService } from "../services/work-item-types.service";
import type { TEpicProgress } from "../types";
import { EpicProgressBar } from "./epic-progress-bar";

const service = new WorkItemTypesService();

/** Progress of an epic's children, shown on the epic's detail page. reloadKey refetches (e.g. child count). */
export function EpicDetailProgress(props: {
  workspaceSlug: string;
  projectId: string;
  epicId: string;
  reloadKey?: unknown;
}) {
  const { workspaceSlug, projectId, epicId, reloadKey } = props;
  const [progress, setProgress] = useState<TEpicProgress>();
  useEffect(() => {
    service
      .epicProgress(workspaceSlug, projectId, epicId)
      .then(setProgress)
      .catch(() => setProgress(undefined));
  }, [workspaceSlug, projectId, epicId, reloadKey]);
  return progress ? <EpicProgressBar progress={progress} /> : null;
}
