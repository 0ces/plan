/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { modulePropertiesStore as store } from "../store/properties.store";
import type { TPropertyValue } from "../types";
import { PropertyValueInput, propertyIcon } from "./property-value-input";

type Props = { workspaceSlug: string; projectId: string; moduleId: string; disabled: boolean };

/** Custom property rows in the module side panel, after the built-in ones. */
export const ModulePropertyValues = observer(function ModulePropertyValues(props: Props) {
  const { workspaceSlug, projectId, moduleId, disabled } = props;

  useEffect(() => {
    void store.fetchForType(workspaceSlug, projectId, projectId);
    void store.fetchValues(workspaceSlug, projectId, moduleId).catch(() => undefined);
  }, [workspaceSlug, projectId, moduleId]);

  const properties = store.getActiveForType(projectId);
  if (!properties.length) return null;
  const values = store.valuesByIssue[moduleId] ?? {};

  const save = (propertyId: string, value: TPropertyValue) => {
    const property = properties.find((p) => p.id === propertyId);
    if (!property) return;
    store.setValue(workspaceSlug, projectId, moduleId, property, value).catch((error: any) => {
      const message = error?.value ?? error?.error ?? "Could not save the value.";
      setToast({ type: TOAST_TYPE.ERROR, title: property.display_name, message: String(message) });
    });
  };

  return (
    <>
      {properties.map((p) => {
        const Icon = propertyIcon(p);
        return (
          <div key={p.id} className="flex items-center justify-start gap-1">
            <div className="flex w-2/5 items-center justify-start gap-2 text-tertiary">
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate text-14">{p.display_name}</span>
            </div>
            <div className="w-3/5">
              <PropertyValueInput
                property={p}
                projectId={projectId}
                value={values[p.id]}
                onChange={(v) => save(p.id, v)}
                disabled={disabled}
                ownerId={moduleId}
              />
            </div>
          </div>
        );
      })}
    </>
  );
});
