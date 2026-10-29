/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { renderFormattedDate } from "@plane/utils";
import { useProject } from "@/hooks/store/use-project";
import { useWorkItemTypes } from "../store/use-work-item-types";
import { epicsStore } from "../store/epics.store";
import { EpicProgressBar } from "./epic-progress-bar";
import { WorkItemTypeIcon } from "./work-item-type-icon";

type Props = { workspaceSlug: string; projectId: string };

export const EpicsList = observer(function EpicsList({ workspaceSlug, projectId }: Props) {
  const types = useWorkItemTypes(workspaceSlug, projectId);
  const { getProjectIdentifierById } = useProject();
  const epics = epicsStore.epicsByProject[projectId];
  const identifier = getProjectIdentifierById(projectId);

  useEffect(() => {
    void epicsStore.fetch(workspaceSlug, projectId);
  }, [workspaceSlug, projectId]);

  if (!types.isEnabled(projectId) || !types.getEpicType(projectId)) {
    return (
      <div className="p-8 text-13 text-tertiary">
        This project has no epic type. Turn on work item types in project settings → Work item types.
      </div>
    );
  }
  if (!epics) return <div className="p-8 text-13 text-tertiary">Loading…</div>;
  if (!epics.length) return <div className="p-8 text-13 text-tertiary">No epics yet. Use “New epic” to add one.</div>;

  return (
    <ul className="divide-y divide-subtle">
      {epics.map((epic) => (
        <li key={epic.id}>
          <Link
            href={`/${workspaceSlug}/browse/${identifier}-${epic.sequence_id}/`}
            className="flex items-center gap-3 px-5 py-3 hover:bg-layer-1"
          >
            <WorkItemTypeIcon typeId={epic.type_id} projectId={projectId} />
            <span className="w-20 shrink-0 text-12 text-tertiary">
              {identifier}-{epic.sequence_id}
            </span>
            <span className="min-w-0 flex-1 truncate text-13 text-primary">{epic.name}</span>
            {epic.target_date && (
              <span className="shrink-0 text-12 text-tertiary">{renderFormattedDate(epic.target_date)}</span>
            )}
            <EpicProgressBar progress={epic.progress} />
          </Link>
        </li>
      ))}
    </ul>
  );
});
