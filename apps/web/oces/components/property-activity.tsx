/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Type } from "lucide-react";
import { IssueActivityBlockComponent } from "@/components/issues/issue-detail/issue-activity/activity/actions";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

const value = (v: string | null | undefined) => <span className="font-medium text-primary">{v}</span>;

/** History row for a custom property change (field "oces_property"; comment = property name). */
export const PropertyActivity = observer(function PropertyActivity({ activityId, ends }: Props) {
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const activity = getActivityById(activityId);
  if (!activity) return null;
  const name = <span className="font-medium text-primary">{activity.comment}</span>;
  return (
    <IssueActivityBlockComponent
      activityId={activityId}
      ends={ends}
      icon={<Type className="size-3.5 text-secondary" aria-hidden="true" />}
    >
      {activity.new_value ? (
        <>
          {" "}
          set {name} to {value(activity.new_value)}.
        </>
      ) : (
        <>
          {" "}
          cleared {name}
          {activity.old_value ? <> (was {value(activity.old_value)})</> : null}.
        </>
      )}
    </IssueActivityBlockComponent>
  );
});
