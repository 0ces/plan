/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import type { TIssuePropertyValueErrors, TIssuePropertyValues } from "@plane/types";
import type {
  TActiveAdditionalPropertiesProps,
  TCreateUpdatePropertyValuesProps,
  TPropertyValuesValidationProps,
} from "@/components/issues/issue-modal/context/issue-modal-context";
import { useIssueModal } from "@/hooks/context/use-issue-modal";
import { defaultValueOf, isEmptyValue, propertiesStore } from "../store/properties.store";
import type { TPropertyValue, TPropertyValues } from "../types";
import { PropertyValueInput } from "./property-value-input";

/** Fills the upstream issue-modal context hooks for custom properties. Used by IssueModalProvider. */
export function useIssueModalProperties() {
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>({});
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});

  const getActiveAdditionalPropertiesLength = useCallback(
    ({ watch }: TActiveAdditionalPropertiesProps) => propertiesStore.getActiveForType(watch("type_id")).length,
    []
  );

  const handlePropertyValuesValidation = useCallback(
    ({ watch }: TPropertyValuesValidationProps) => {
      const errors: Record<string, string> = {};
      for (const p of propertiesStore.getActiveForType(watch("type_id"))) {
        if (p.is_required && isEmptyValue(issuePropertyValues[p.id] as TPropertyValue)) errors[p.id] = "Required";
      }
      setIssuePropertyValueErrors(errors as TIssuePropertyValueErrors);
      return Object.keys(errors).length === 0;
    },
    [issuePropertyValues]
  );

  const handleCreateUpdatePropertyValues = useCallback(
    async ({ issueId, projectId, workspaceSlug, issueTypeId }: TCreateUpdatePropertyValuesProps) => {
      if (!issueTypeId || !propertiesStore.getActiveForType(issueTypeId).length) return;
      await propertiesStore.saveAll(
        workspaceSlug,
        projectId,
        issueId,
        issueTypeId,
        issuePropertyValues as TPropertyValues
      );
      setIssuePropertyValues({});
      setIssuePropertyValueErrors({});
    },
    [issuePropertyValues]
  );

  return {
    issuePropertyValues,
    setIssuePropertyValues,
    issuePropertyValueErrors,
    setIssuePropertyValueErrors,
    getActiveAdditionalPropertiesLength,
    handlePropertyValuesValidation,
    handleCreateUpdatePropertyValues,
  };
}

type FieldsProps = {
  workspaceSlug: string;
  projectId: string | null;
  typeId: string | null | undefined;
  issueId?: string;
};

/** Property inputs in the create/edit modal, below the description. */
export const IssueModalPropertyFields = observer(function IssueModalPropertyFields(props: FieldsProps) {
  const { workspaceSlug, projectId, typeId, issueId } = props;
  const { issuePropertyValues, setIssuePropertyValues, issuePropertyValueErrors } = useIssueModal();
  const filledFor = useRef<string | null>(null);

  useEffect(() => {
    if (workspaceSlug && projectId && typeId) void propertiesStore.fetchForType(workspaceSlug, projectId, typeId);
  }, [workspaceSlug, projectId, typeId]);

  const properties = propertiesStore.getActiveForType(typeId);

  // Start from the work item's saved values (edit) or the type's defaults (create), once per type.
  useEffect(() => {
    const key = `${issueId ?? "new"}:${typeId}`;
    if (!typeId || !properties.length || filledFor.current === key) return;
    filledFor.current = key;
    const start = async () => {
      let values: TPropertyValues = {};
      if (issueId && projectId) {
        await propertiesStore.fetchValues(workspaceSlug, projectId, issueId).catch(() => undefined);
        values = { ...propertiesStore.valuesByIssue[issueId] };
      } else {
        for (const p of properties) {
          const d = defaultValueOf(p);
          if (d !== undefined) values[p.id] = d;
        }
      }
      setIssuePropertyValues(values);
    };
    void start();
  }, [issueId, typeId, properties, projectId, workspaceSlug, setIssuePropertyValues]);

  if (!projectId || !properties.length) return null;
  const errors = issuePropertyValueErrors as Record<string, string | undefined>;

  return (
    <div className="grid grid-cols-1 gap-x-3 gap-y-2 px-5 sm:grid-cols-2">
      {properties.map((p) => (
        <div key={p.id} className="flex flex-col gap-1">
          <span className="text-caption-sm-medium text-tertiary">
            {p.display_name}
            {p.is_required && <span className="text-danger-primary"> *</span>}
          </span>
          <PropertyValueInput
            property={p}
            projectId={projectId}
            value={issuePropertyValues[p.id] as TPropertyValue}
            onChange={(v) => setIssuePropertyValues((prev) => ({ ...prev, [p.id]: v }))}
            variant="form"
            error={errors[p.id]}
          />
          {errors[p.id] && <span className="text-caption-sm-regular text-danger-primary">{errors[p.id]}</span>}
        </div>
      ))}
    </div>
  );
});
