/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Logo } from "@plane/propel/emoji-icon-picker";
import type { TLogoProps } from "@plane/types";
import { CustomSelect } from "@plane/ui";
import { useWorkItemTypes } from "../store/use-work-item-types";

type Props = {
  projectId: string | null | undefined;
  value: string | null | undefined;
  onChange: (typeId: string) => void;
  disabled?: boolean;
};

/** Type picker. Hidden when the project has types off. */
export const WorkItemTypeSelect = observer(function WorkItemTypeSelect(props: Props) {
  const { projectId, value, onChange, disabled = false } = props;
  const { workspaceSlug } = useParams();
  const store = useWorkItemTypes(workspaceSlug, projectId);
  if (!projectId || !store.isEnabled(projectId)) return null;
  const types = store.getActiveTypes(projectId);
  const selected = store.getTypeById(value) ?? store.getDefaultType(projectId);
  return (
    <CustomSelect
      value={selected?.id}
      onChange={(typeId: string) => onChange(typeId)}
      disabled={disabled}
      maxHeight="lg"
      buttonClassName="border-[0.5px] border-subtle rounded-md px-2 py-1 text-13"
      label={
        <span className="flex items-center gap-1.5">
          {selected && <Logo logo={selected.logo_props as TLogoProps} size={14} />}
          <span>{selected?.name ?? "Type"}</span>
        </span>
      }
    >
      {types.map((type) => (
        <CustomSelect.Option key={type.id} value={type.id}>
          <span className="flex items-center gap-1.5">
            <Logo logo={type.logo_props as TLogoProps} size={14} />
            <span>{type.name}</span>
          </span>
        </CustomSelect.Option>
      ))}
    </CustomSelect>
  );
});
