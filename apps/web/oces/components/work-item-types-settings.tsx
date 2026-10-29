/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@plane/propel/button";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TLogoProps } from "@plane/types";
import { CustomMenu, ToggleSwitch } from "@plane/ui";
import { useWorkItemTypes } from "../store/use-work-item-types";
import type { TWorkItemType } from "../types";
import { WorkItemTypeModal } from "./work-item-type-modal";

type Props = { workspaceSlug: string; projectId: string };

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 text-secondary">{children}</span>;
}

export const WorkItemTypesSettings = observer(function WorkItemTypesSettings({ workspaceSlug, projectId }: Props) {
  const store = useWorkItemTypes(workspaceSlug, projectId);
  const [modal, setModal] = useState<{ open: boolean; type?: TWorkItemType }>({ open: false });
  const [toggling, setToggling] = useState(false);
  const enabled = store.isEnabled(projectId);
  const types = store.getProjectTypes(projectId);

  const run = async (action: () => Promise<unknown>, failure: string) => {
    try {
      await action();
    } catch (error: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: error?.error ?? failure });
    }
  };

  const toggle = async () => {
    setToggling(true);
    await run(() => store.setEnabled(workspaceSlug, projectId, !enabled), "Could not change the setting.");
    setToggling(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 rounded-lg border-[0.5px] border-subtle p-4">
        <div>
          <h4 className="text-14 font-medium text-primary">Enable work item types</h4>
          <p className="text-13 text-tertiary">
            Adds Task, Bug, Feature and Epic. Existing work items become Tasks. Epics get their own page with progress.
          </p>
        </div>
        <ToggleSwitch value={enabled} onChange={toggle} disabled={toggling} size="sm" />
      </div>

      {enabled && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-14 font-medium text-primary">Types</h4>
            <Button variant="primary" size="sm" onClick={() => setModal({ open: true })}>
              Add type
            </Button>
          </div>
          <ul className="divide-y divide-subtle rounded-lg border-[0.5px] border-subtle">
            {types.map((type) => (
              <li key={type.id} className="flex items-center gap-3 px-4 py-3">
                <Logo logo={type.logo_props as TLogoProps} size={18} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-13 font-medium ${type.is_active ? "text-primary" : "text-tertiary"}`}>
                      {type.name}
                    </span>
                    {type.is_default && <Badge>Default</Badge>}
                    {type.is_epic && <Badge>Epic</Badge>}
                    {!type.is_active && <Badge>Inactive</Badge>}
                  </div>
                  {type.description && <p className="truncate text-12 text-tertiary">{type.description}</p>}
                </div>
                <CustomMenu ellipsis placement="bottom-end">
                  <CustomMenu.MenuItem onClick={() => setModal({ open: true, type })}>Edit</CustomMenu.MenuItem>
                  {!type.is_default && !type.is_epic && type.is_active && (
                    <CustomMenu.MenuItem
                      onClick={() =>
                        run(
                          () => store.update(workspaceSlug, projectId, type.id, { is_default: true }),
                          "Could not change the default."
                        )
                      }
                    >
                      Make default
                    </CustomMenu.MenuItem>
                  )}
                  {!type.is_default && (
                    <CustomMenu.MenuItem
                      onClick={() =>
                        run(
                          () => store.update(workspaceSlug, projectId, type.id, { is_active: !type.is_active }),
                          "Could not change the type."
                        )
                      }
                    >
                      {type.is_active ? "Deactivate" : "Activate"}
                    </CustomMenu.MenuItem>
                  )}
                  {!type.is_default && (
                    <CustomMenu.MenuItem
                      onClick={() => run(() => store.remove(workspaceSlug, projectId, type.id), "Could not delete.")}
                    >
                      <span className="text-danger-primary">Delete</span>
                    </CustomMenu.MenuItem>
                  )}
                </CustomMenu>
              </li>
            ))}
          </ul>
        </div>
      )}

      <WorkItemTypeModal
        isOpen={modal.open}
        type={modal.type}
        onClose={() => setModal({ open: false })}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
      />
    </div>
  );
});
