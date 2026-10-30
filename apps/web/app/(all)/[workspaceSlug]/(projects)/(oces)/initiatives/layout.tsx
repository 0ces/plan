/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { InitiativesHeader } from "@oces/components/initiatives-list";

export default function InitiativesLayout() {
  return (
    <>
      <AppHeader header={<InitiativesHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
