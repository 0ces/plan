/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PageHead } from "@/components/core/page-title";
import { InitiativesList } from "@oces/components/initiatives-list";
import type { Route } from "./+types/page";

export default function InitiativesPage({ params }: Route.ComponentProps) {
  return (
    <>
      <PageHead title="Initiatives" />
      <InitiativesList workspaceSlug={params.workspaceSlug} />
    </>
  );
}
