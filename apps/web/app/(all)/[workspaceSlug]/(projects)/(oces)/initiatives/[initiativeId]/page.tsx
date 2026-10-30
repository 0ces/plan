/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { InitiativeDetail } from "@oces/components/initiative-detail";
import { initiativesStore } from "@oces/store/initiatives.store";
import type { Route } from "./+types/page";

function InitiativePage({ params }: Route.ComponentProps) {
  const { workspaceSlug, initiativeId } = params;
  const name = initiativesStore.byId[initiativeId]?.name;
  return (
    <>
      <PageHead title={name ? `${name} - Initiatives` : "Initiatives"} />
      <InitiativeDetail workspaceSlug={workspaceSlug} initiativeId={initiativeId} />
    </>
  );
}

export default observer(InitiativePage);
