/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Controller } from "react-hook-form";
import type { Control } from "react-hook-form";
import type { TIssue } from "@plane/types";
import { WorkItemTypeSelect } from "./work-item-type-select";

type Props = {
  control: Control<TIssue>;
  projectId: string | null | undefined;
  disabled?: boolean;
  handleFormChange?: () => void;
};

/** Type picker inside the create/edit work item modal (field type_id). */
export function WorkItemTypeFormField({ control, projectId, disabled, handleFormChange }: Props) {
  return (
    <Controller
      control={control}
      name="type_id"
      render={({ field: { value, onChange } }) => (
        <WorkItemTypeSelect
          projectId={projectId}
          value={value}
          disabled={disabled}
          onChange={(typeId) => {
            onChange(typeId);
            handleFormChange?.();
          }}
        />
      )}
    />
  );
}
