/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { Tooltip } from "@plane/propel/tooltip";
import { useMember } from "@/hooks/store/use-member";
import { useModule } from "@/hooks/store/use-module";
import { fetchModuleListValues, isEmptyValue, modulePropertiesStore as store } from "../store/properties.store";
import type { TProperty, TPropertyValue } from "../types";

type Props = { workspaceSlug: string; projectId: string; moduleId: string };

const MAX_CHIPS = 3;
const loaded: Record<string, Promise<void> | undefined> = {};

/** The module's filled-in property values as small chips in the module list. */
export const ModulePropertyChips = observer(function ModulePropertyChips({
  workspaceSlug,
  projectId,
  moduleId,
}: Props) {
  const { getUserDetails } = useMember();
  const { getModuleById } = useModule();

  useEffect(() => {
    void store.fetchForType(workspaceSlug, projectId, projectId);
    // one call for the whole list, not one per row
    loaded[projectId] ??= fetchModuleListValues(workspaceSlug, projectId).catch(() => {
      loaded[projectId] = undefined;
    });
  }, [workspaceSlug, projectId]);

  const values = store.valuesByIssue[moduleId] ?? {};
  const text = (p: TProperty, v: TPropertyValue): string => {
    const list = (Array.isArray(v) ? v : [v]).map(String);
    if (p.property_type === "OPTION")
      return p.options
        .filter((o) => list.includes(o.id))
        .map((o) => o.name)
        .join(", ");
    if (p.property_type === "BOOLEAN") return v === true ? "Yes" : "No";
    if (p.relation_type === "USER") return list.map((id) => getUserDetails(id)?.display_name ?? "").join(", ");
    if (p.relation_type === "MODULE") return list.map((id) => getModuleById(id)?.name ?? "").join(", ");
    if (p.relation_type === "ISSUE") return `${list.length} work item${list.length > 1 ? "s" : ""}`;
    return list.join(", ");
  };

  const chips = store
    .getActiveForType(projectId)
    .filter((p) => !isEmptyValue(values[p.id]) && p.settings?.display_format !== "multi-line")
    .map((p) => ({ id: p.id, name: p.display_name, value: text(p, values[p.id]) }))
    .filter((c) => c.value);
  if (!chips.length) return null;

  return (
    <div className="hidden max-w-80 items-center gap-1 overflow-hidden md:flex">
      {chips.slice(0, MAX_CHIPS).map((c) => (
        <Tooltip key={c.id} tooltipHeading={c.name} tooltipContent={c.value}>
          <span className="h-6 max-w-32 truncate rounded-sm border-[0.5px] border-strong px-1.5 text-11 leading-6 text-tertiary">
            {c.value}
          </span>
        </Tooltip>
      ))}
      {chips.length > MAX_CHIPS && <span className="text-11 text-tertiary">+{chips.length - MAX_CHIPS}</span>}
    </div>
  );
});
