/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { EIconSize, STATE_GROUPS } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { StateGroupIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { useProjectState } from "@/hooks/store/use-project-state";
import { boardOrderStore as store, orderStateColumns } from "../store/board-order.store";

type Props = { workspaceSlug: string; projectId: string };

/** Reorder the state columns of the project's board (and list) when grouped by state. */
export const BoardColumnsSettings = observer(function BoardColumnsSettings({ workspaceSlug, projectId }: Props) {
  const { getProjectStates, fetchProjectStates } = useProjectState();

  useEffect(() => {
    void fetchProjectStates(workspaceSlug, projectId);
  }, [workspaceSlug, projectId, fetchProjectStates]);

  const states = orderStateColumns(workspaceSlug, projectId, getProjectStates(projectId) ?? []);
  const custom = (store.byProject[projectId] ?? []).length > 0;

  const save = (ids: string[]) =>
    store.save(workspaceSlug, projectId, ids).catch((error: any) => {
      const message = error?.state_ids ?? error?.error ?? "Could not save the order.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Board columns", message: String(message) });
    });

  const move = (index: number, by: number) => {
    const ids = states.map((s) => s.id);
    const [id] = ids.splice(index, 1);
    ids.splice(index + by, 0, id);
    void save(ids);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-md border-[0.5px] border-subtle">
        {states.map((state, i) => (
          <div
            key={state.id}
            className="flex items-center gap-3 border-b-[0.5px] border-subtle px-4 py-2.5 last:border-b-0"
          >
            <span className="w-5 text-right text-caption-sm-regular text-tertiary tabular-nums">{i + 1}</span>
            <StateGroupIcon stateGroup={state.group} color={state.color} size={EIconSize.LG} />
            <span className="flex-1 text-body-sm-medium text-primary">{state.name}</span>
            <span className="text-caption-sm-regular text-tertiary">{STATE_GROUPS[state.group]?.label}</span>
            <div className="flex gap-1">
              <button
                type="button"
                aria-label={`Move ${state.name} left`}
                disabled={i === 0}
                onClick={() => move(i, -1)}
                className="rounded-sm p-1 text-tertiary hover:bg-layer-transparent-hover disabled:opacity-30"
              >
                <ArrowUp className="size-3.5" />
              </button>
              <button
                type="button"
                aria-label={`Move ${state.name} right`}
                disabled={i === states.length - 1}
                onClick={() => move(i, 1)}
                className="rounded-sm p-1 text-tertiary hover:bg-layer-transparent-hover disabled:opacity-30"
              >
                <ArrowDown className="size-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
      {custom && (
        <div>
          <Button variant="secondary" size="sm" onClick={() => void save([])}>
            Reset to default order
          </Button>
        </div>
      )}
    </div>
  );
});
