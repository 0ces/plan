/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { TypePropertiesEditor } from "@oces/components/type-properties-editor";
import type { Route } from "./+types/page";

function ModulePropertiesSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails } = useProject();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);

  if (workspaceUserInfo && !isAdmin) return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;

  return (
    <SettingsContentWrapper>
      <PageHead
        title={currentProjectDetails?.name ? `${currentProjectDetails.name} settings - Module properties` : undefined}
      />
      <section className="w-full">
        <SettingsHeading
          title="Module properties"
          description="Fields every module in this project can fill in, like priority, depends on or suggested order. Work item counts, points and progress are computed from each module's work items."
        />
        <div className="mt-7 overflow-hidden rounded-md border-[0.5px] border-subtle">
          <TypePropertiesEditor workspaceSlug={workspaceSlug} projectId={projectId} forModules />
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(ModulePropertiesSettingsPage);
