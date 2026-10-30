/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Target } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { SidebarNavItem } from "@/components/sidebar/sidebar-navigation";
import { useUserPermissions } from "@/hooks/store/user";

/** "Initiatives" in the workspace sidebar, for members and admins (never guests). The page offers to switch them on. */
export const InitiativesNavItem = observer(function InitiativesNavItem() {
  const { workspaceSlug } = useParams();
  const pathname = usePathname();
  const { allowPermissions } = useUserPermissions();
  const slug = workspaceSlug?.toString() ?? "";
  const allowed = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE,
    slug
  );

  if (!slug || !allowed) return null;
  const href = `/${slug}/initiatives/`;
  return (
    <Link href={href}>
      <SidebarNavItem isActive={pathname.includes(`/${slug}/initiatives`)}>
        <div className="flex items-center gap-1.5 py-[1px]">
          <Target className="size-4 flex-shrink-0" />
          <p className="text-13 leading-5 font-medium">Initiatives</p>
        </div>
      </SidebarNavItem>
    </Link>
  );
});
