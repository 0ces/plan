/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { propertiesStore } from "../store/properties.store";
import type { TPropertyValue } from "../types";
import { PropertyValueInput, propertyIcon } from "./property-value-input";
import { WorkItemPullRequests } from "./work-item-pull-requests";
import { WorkItemTimeLog } from "./work-item-time-log";

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled: boolean };

/** Custom property rows (plus time log and pull requests) in the work item sidebar and peek panel, after the built-in ones. */
export const WorkItemPropertyValues = observer(function WorkItemPropertyValues(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled } = props;
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const typeId = getIssueById(issueId)?.type_id;

  useEffect(() => {
    if (!typeId) return;
    void propertiesStore.fetchForType(workspaceSlug, projectId, typeId);
    void propertiesStore.fetchValues(workspaceSlug, projectId, issueId).catch(() => undefined);
  }, [workspaceSlug, projectId, issueId, typeId]);

  const properties = propertiesStore.getActiveForType(typeId);
  const values = propertiesStore.valuesByIssue[issueId] ?? {};

  const save = (propertyId: string, value: TPropertyValue) => {
    const property = properties.find((p) => p.id === propertyId);
    if (!property) return;
    propertiesStore.setValue(workspaceSlug, projectId, issueId, property, value).catch((error: any) => {
      const message = error?.value ?? error?.error ?? "Could not save the value.";
      setToast({ type: TOAST_TYPE.ERROR, title: property.display_name, message: String(message) });
    });
  };

  return (
    <>
      {properties.map((p) => (
        <SidebarPropertyListItem key={p.id} icon={propertyIcon(p)} label={p.display_name}>
          <PropertyValueInput
            property={p}
            projectId={projectId}
            value={values[p.id]}
            onChange={(v) => save(p.id, v)}
            disabled={disabled}
          />
        </SidebarPropertyListItem>
      ))}
      <WorkItemTimeLog workspaceSlug={workspaceSlug} projectId={projectId} issueId={issueId} />
      <WorkItemPullRequests workspaceSlug={workspaceSlug} projectId={projectId} issueId={issueId} />
    </>
  );
});
