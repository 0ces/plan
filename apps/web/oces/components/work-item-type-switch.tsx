/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "react-router";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { workItemTypesStore } from "../store/work-item-types.store";
import { EpicDetailProgress } from "./epic-detail-progress";
import { WorkItemTypeSelect } from "./work-item-type-select";

/** Change a work item's type from its detail page. */
export const WorkItemTypeSwitch = observer(function WorkItemTypeSwitch(props: { issueId: string; disabled: boolean }) {
  const { issueId, disabled } = props;
  const { workspaceSlug } = useParams();
  const {
    issue: { getIssueById, updateIssue },
  } = useIssueDetail();
  const issue = getIssueById(issueId);
  if (!issue?.project_id || !workspaceSlug) return null;
  const projectId = issue.project_id;
  const isEpic = !!workItemTypesStore.getTypeById(issue.type_id)?.is_epic;
  return (
    <div className="flex items-center gap-3">
      <WorkItemTypeSelect
        projectId={projectId}
        value={issue.type_id}
        disabled={disabled}
        onChange={(typeId) => {
          if (typeId === issue.type_id) return;
          updateIssue(workspaceSlug, projectId, issueId, { type_id: typeId }).catch(() =>
            setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not change the type." })
          );
        }}
      />
      {isEpic && (
        <EpicDetailProgress
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          epicId={issueId}
          reloadKey={issue.sub_issues_count}
        />
      )}
    </div>
  );
});
