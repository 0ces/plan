/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { Tooltip } from "@plane/propel/tooltip";
import type { TLogoProps } from "@plane/types";
import { useWorkItemTypes } from "../store/use-work-item-types";

type Props = { typeId?: string | null; projectId?: string | null; size?: number };

/** Small type icon shown before a work item identifier. Renders nothing when types are off. */
export const WorkItemTypeIcon = observer(function WorkItemTypeIcon({ typeId, projectId, size = 14 }: Props) {
  const { workspaceSlug } = useParams();
  const store = useWorkItemTypes(workspaceSlug, projectId);
  const type = store.getTypeById(typeId);
  if (!type || !projectId || !store.isEnabled(projectId)) return null;
  return (
    <Tooltip tooltipContent={type.name}>
      <span className="flex shrink-0 items-center" aria-label={type.name}>
        <Logo logo={type.logo_props as TLogoProps} size={size} />
      </span>
    </Tooltip>
  );
});
