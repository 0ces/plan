/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// store hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// components
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// OCES: type picker (docs/fork/UPSTREAM_EDITS.md)
import { WorkItemTypeSwitch } from "@oces/components/work-item-type-switch";

export type TIssueTypeSwitcherProps = {
  issueId: string;
  disabled: boolean;
};

export const IssueTypeSwitcher = observer(function IssueTypeSwitcher(props: TIssueTypeSwitcherProps) {
  const { issueId, disabled } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // derived values
  const issue = getIssueById(issueId);

  if (!issue || !issue.project_id) return <></>;

  return (
    <div className="flex items-center gap-2">
      <IssueIdentifier issueId={issueId} projectId={issue.project_id} size="md" enableClickToCopyIdentifier />
      {/* OCES: type picker */}
      <WorkItemTypeSwitch issueId={issueId} disabled={disabled} />
    </div>
  );
});
