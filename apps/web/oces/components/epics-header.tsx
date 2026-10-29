/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Button } from "@plane/propel/button";
import { EpicIcon } from "@plane/propel/icons";
import { Breadcrumbs, Header } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";
import { useWorkItemTypes } from "../store/use-work-item-types";
import { epicsStore } from "../store/epics.store";

export const EpicsHeader = observer(function EpicsHeader() {
  const { workspaceSlug, projectId } = useParams();
  const types = useWorkItemTypes(workspaceSlug, projectId);
  const [open, setOpen] = useState(false);
  const epicType = projectId ? types.getEpicType(projectId) : undefined;
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label="Epics" icon={<EpicIcon className="size-4" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
      <Header.RightItem>
        {epicType && (
          <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
            New epic
          </Button>
        )}
      </Header.RightItem>
      {epicType && projectId && workspaceSlug && (
        <CreateUpdateIssueModal
          isOpen={open}
          onClose={() => setOpen(false)}
          data={{ project_id: projectId, type_id: epicType.id }}
          modalTitle="Create epic"
          isProjectSelectionDisabled
          onSubmit={async () => epicsStore.fetch(workspaceSlug, projectId)}
        />
      )}
    </Header>
  );
});
