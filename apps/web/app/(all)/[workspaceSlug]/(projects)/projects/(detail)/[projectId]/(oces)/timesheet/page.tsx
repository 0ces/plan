/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { useProject } from "@/hooks/store/use-project";
import { Timesheet } from "@oces/components/timesheet";
import type { Route } from "./+types/page";

function ProjectTimesheetPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { getProjectById } = useProject();
  const project = getProjectById(projectId);
  return (
    <>
      <PageHead title={project?.name ? `${project.name} - Timesheet` : undefined} />
      <Timesheet workspaceSlug={workspaceSlug} projectId={projectId} />
    </>
  );
}

export default observer(ProjectTimesheetPage);
