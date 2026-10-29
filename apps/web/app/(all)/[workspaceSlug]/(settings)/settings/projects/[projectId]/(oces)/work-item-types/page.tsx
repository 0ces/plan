/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { WorkItemTypesSettings } from "@oces/components/work-item-types-settings";
import type { Route } from "./+types/page";

function WorkItemTypesSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails } = useProject();
  const { t } = useTranslation();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);

  if (workspaceUserInfo && !isAdmin) return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;

  return (
    <SettingsContentWrapper>
      <PageHead
        title={currentProjectDetails?.name ? `${currentProjectDetails.name} settings - Work item types` : undefined}
      />
      <section className="w-full">
        <SettingsHeading
          title={t("project_settings.work_item_types.heading")}
          description={t("project_settings.work_item_types.description")}
        />
        <div className="mt-7">
          <WorkItemTypesSettings workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(WorkItemTypesSettingsPage);
