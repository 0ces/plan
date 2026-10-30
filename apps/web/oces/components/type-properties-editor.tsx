/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AlertModalCore, CustomMenu } from "@plane/ui";
import { propertiesStore } from "../store/properties.store";
import type { TProperty } from "../types";
import { PropertyModal, kindOf } from "./property-modal";
import { propertyIcon } from "./property-value-input";

type Props = { workspaceSlug: string; projectId: string; typeId: string };

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 text-secondary">{children}</span>;
}

/** The custom properties of one work item type, inside the type's row in settings. */
export const TypePropertiesEditor = observer(function TypePropertiesEditor({
  workspaceSlug,
  projectId,
  typeId,
}: Props) {
  const [modal, setModal] = useState<{ open: boolean; property?: TProperty }>({ open: false });
  const [deleting, setDeleting] = useState<TProperty | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void propertiesStore.fetchForType(workspaceSlug, projectId, typeId);
  }, [workspaceSlug, projectId, typeId]);

  const properties = propertiesStore.getForType(typeId);

  const run = async (action: () => Promise<unknown>, failure: string) => {
    try {
      await action();
    } catch (error: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: String(Object.values(error ?? {})[0] ?? failure) });
    }
  };

  /** Swap sort_order with the neighbour. */
  const move = (index: number, delta: -1 | 1) => {
    const a = properties[index];
    const b = properties[index + delta];
    if (!a || !b) return;
    void run(async () => {
      await propertiesStore.update(workspaceSlug, projectId, typeId, a.id, { sort_order: b.sort_order });
      await propertiesStore.update(workspaceSlug, projectId, typeId, b.id, { sort_order: a.sort_order });
    }, "Could not reorder.");
  };

  return (
    <div className="space-y-2 bg-layer-1 px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="text-12 font-medium text-tertiary">Properties</span>
        <Button variant="secondary" size="sm" onClick={() => setModal({ open: true })}>
          Add property
        </Button>
      </div>
      {properties.length === 0 ? (
        <p className="text-12 text-tertiary">No properties yet. Add fields like Client, Size or Due week.</p>
      ) : (
        <ul className="divide-y divide-subtle rounded-md border-[0.5px] border-subtle bg-surface-1">
          {properties.map((p, i) => {
            const Icon = propertyIcon(p);
            return (
              <li key={p.id} className="flex items-center gap-3 px-3 py-2">
                <Icon className="size-4 shrink-0 text-tertiary" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-13 ${p.is_active ? "text-primary" : "text-tertiary"}`}>
                      {p.display_name}
                    </span>
                    <span className="text-12 text-tertiary">{kindOf(p).label}</span>
                    {p.is_required && <Badge>Required</Badge>}
                    {p.is_multi && <Badge>Multiple</Badge>}
                    {!p.is_active && <Badge>Inactive</Badge>}
                  </div>
                  {p.property_type === "OPTION" && (
                    <p className="truncate text-12 text-tertiary">{p.options.map((o) => o.name).join(", ")}</p>
                  )}
                </div>
                <CustomMenu ellipsis placement="bottom-end">
                  <CustomMenu.MenuItem onClick={() => setModal({ open: true, property: p })}>Edit</CustomMenu.MenuItem>
                  {i > 0 && <CustomMenu.MenuItem onClick={() => move(i, -1)}>Move up</CustomMenu.MenuItem>}
                  {i < properties.length - 1 && (
                    <CustomMenu.MenuItem onClick={() => move(i, 1)}>Move down</CustomMenu.MenuItem>
                  )}
                  <CustomMenu.MenuItem
                    onClick={() =>
                      run(
                        () =>
                          propertiesStore.update(workspaceSlug, projectId, typeId, p.id, { is_active: !p.is_active }),
                        "Could not change the property."
                      )
                    }
                  >
                    {p.is_active ? "Deactivate" : "Activate"}
                  </CustomMenu.MenuItem>
                  <CustomMenu.MenuItem onClick={() => setDeleting(p)}>
                    <span className="text-danger-primary">Delete</span>
                  </CustomMenu.MenuItem>
                </CustomMenu>
              </li>
            );
          })}
        </ul>
      )}

      <PropertyModal
        isOpen={modal.open}
        property={modal.property}
        onClose={() => setModal({ open: false })}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        typeId={typeId}
      />
      <AlertModalCore
        isOpen={!!deleting}
        handleClose={() => setDeleting(null)}
        isSubmitting={busy}
        title={`Delete "${deleting?.display_name}"?`}
        content="Its values are removed from every work item. To keep them, deactivate the property instead."
        primaryButtonText={{ loading: "Deleting", default: "Delete" }}
        handleSubmit={async () => {
          if (!deleting) return;
          setBusy(true);
          await run(() => propertiesStore.remove(workspaceSlug, projectId, typeId, deleting.id), "Could not delete.");
          setBusy(false);
          setDeleting(null);
        }}
      />
    </div>
  );
});
