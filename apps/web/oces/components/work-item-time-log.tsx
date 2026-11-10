/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Pencil, Timer, Trash2 } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EModalPosition, EModalWidth, Input, ModalCore } from "@plane/ui";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { ButtonAvatars } from "@/components/dropdowns/member/avatar";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { formatDuration, parseDuration, todayIso, workLogsStore as store } from "../store/worklogs.store";
import type { TWorkLog } from "../types";

type Props = { workspaceSlug: string; projectId: string; issueId: string };

const errorText = (error: any) =>
  String(
    error?.duration ?? error?.logged_at ?? error?.description ?? error?.error ?? error?.detail ?? "Could not save."
  );

/** "Time logged" row in the work item sidebar and peek panel. Only when the project has time tracking on. */
export const WorkItemTimeLog = observer(function WorkItemTimeLog({ workspaceSlug, projectId, issueId }: Props) {
  const { getProjectById } = useProject();
  const { allowPermissions } = useUserPermissions();
  const [open, setOpen] = useState(false);
  const enabled = !!getProjectById(projectId)?.is_time_tracking_enabled;
  const canLog = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  useEffect(() => {
    if (enabled && canLog) void store.fetchLogs(workspaceSlug, projectId, issueId).catch(() => undefined);
  }, [enabled, canLog, workspaceSlug, projectId, issueId]);

  if (!enabled || !canLog) return null;
  const total = store.total(projectId, issueId);

  return (
    <SidebarPropertyListItem icon={Timer} label="Time logged">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="h-7.5 rounded-sm px-2 text-body-xs-regular text-secondary hover:bg-layer-transparent-hover"
      >
        {total ? formatDuration(total) : <span className="text-placeholder">Log time</span>}
      </button>
      <TimeLogModal
        isOpen={open}
        onClose={() => setOpen(false)}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        issueId={issueId}
      />
    </SidebarPropertyListItem>
  );
});

type ModalProps = Props & { isOpen: boolean; onClose: () => void };

const TimeLogModal = observer(function TimeLogModal(props: ModalProps) {
  const { isOpen, onClose, workspaceSlug, projectId, issueId } = props;
  const { data: currentUser } = useUser();
  const { getUserDetails } = useMember();
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);
  const [editing, setEditing] = useState<TWorkLog | null>(null);
  const [duration, setDuration] = useState("");
  const [date, setDate] = useState(todayIso());
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const reset = (log: TWorkLog | null = null) => {
    setEditing(log);
    setDuration(log ? formatDuration(log.duration) : "");
    setDate(log?.logged_at ?? todayIso());
    setNote(log?.description ?? "");
  };

  useEffect(() => {
    if (isOpen) reset();
  }, [isOpen]);

  const logs = store.logsByIssue[issueId] ?? [];
  const minutes = parseDuration(duration);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!minutes) return;
    setSaving(true);
    const data = { duration: minutes, logged_at: date, description: note };
    try {
      if (editing) await store.update(workspaceSlug, projectId, issueId, editing.id, data);
      else await store.create(workspaceSlug, projectId, issueId, data);
      reset();
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Time log", message: errorText(error) });
    } finally {
      setSaving(false);
    }
  };

  const remove = (log: TWorkLog) =>
    store.remove(workspaceSlug, projectId, issueId, log.id).catch((error) => {
      setToast({ type: TOAST_TYPE.ERROR, title: "Time log", message: errorText(error) });
    });

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <div className="flex flex-col gap-4 p-5">
        <div className="flex items-baseline justify-between">
          <h3 className="text-h5-medium text-primary">Time logged</h3>
          <span className="text-body-sm-medium text-secondary">
            Total {formatDuration(store.total(projectId, issueId))}
          </span>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-2 rounded-md border border-subtle p-3">
          <div className="flex flex-wrap gap-2">
            <div className="flex w-32 flex-col gap-1">
              <label htmlFor="oces-worklog-duration" className="text-caption-sm-medium text-tertiary">
                Time spent
              </label>
              <Input
                id="oces-worklog-duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="1h 30m"
                hasError={!!duration && !minutes}
              />
            </div>
            <div className="flex w-40 flex-col gap-1">
              <label htmlFor="oces-worklog-date" className="text-caption-sm-medium text-tertiary">
                Date
              </label>
              <Input
                id="oces-worklog-date"
                type="date"
                value={date}
                max={todayIso()}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="flex min-w-48 flex-1 flex-col gap-1">
              <label htmlFor="oces-worklog-note" className="text-caption-sm-medium text-tertiary">
                Note
              </label>
              <Input
                id="oces-worklog-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What did you work on?"
                maxLength={2000}
              />
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-caption-sm-regular text-tertiary">
              {duration && !minutes ? "Use 1h 30m, 45m, 1.5h or 1:30." : minutes ? formatDuration(minutes) : ""}
            </span>
            <div className="flex gap-2">
              {editing && (
                <Button variant="secondary" size="sm" type="button" onClick={() => reset()}>
                  Cancel
                </Button>
              )}
              <Button variant="primary" size="sm" type="submit" disabled={!minutes || !date} loading={saving}>
                {editing ? "Save" : "Log time"}
              </Button>
            </div>
          </div>
        </form>

        <div className="flex max-h-80 flex-col overflow-y-auto">
          {logs.length === 0 && (
            <p className="py-4 text-center text-body-sm-regular text-tertiary">No time logged yet.</p>
          )}
          {logs.map((log) => {
            const mine = log.logged_by === currentUser?.id;
            return (
              <div key={log.id} className="flex items-center gap-3 border-b border-subtle py-2 last:border-b-0">
                <ButtonAvatars showTooltip userIds={log.logged_by} />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="text-body-sm-medium text-primary">
                    {formatDuration(log.duration)}
                    <span className="ml-2 text-body-xs-regular text-tertiary">
                      {getUserDetails(log.logged_by)?.display_name} · {log.logged_at}
                    </span>
                  </span>
                  {log.description && (
                    <span className="truncate text-body-xs-regular text-secondary">{log.description}</span>
                  )}
                </div>
                {(mine || isAdmin) && (
                  <div className="flex gap-1">
                    <button
                      type="button"
                      aria-label="Edit time log"
                      onClick={() => reset(log)}
                      className="rounded-sm p-1 text-tertiary hover:bg-layer-transparent-hover"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      aria-label="Delete time log"
                      onClick={() => void remove(log)}
                      className="rounded-sm p-1 text-tertiary hover:bg-layer-transparent-hover hover:text-danger-primary"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </ModalCore>
  );
});

/** Small total in the work item list, from one summary request per project. */
export const WorkItemTimeChip = observer(function WorkItemTimeChip({ workspaceSlug, projectId, issueId }: Props) {
  const { getProjectById } = useProject();
  const enabled = !!getProjectById(projectId)?.is_time_tracking_enabled;
  useEffect(() => {
    if (enabled) void store.fetchSummary(workspaceSlug, projectId);
  }, [enabled, workspaceSlug, projectId]);
  const total = enabled ? store.total(projectId, issueId) : 0;
  if (!total) return null;
  return (
    <span
      title="Time logged"
      className="flex h-5 items-center gap-1 rounded-sm border-[0.5px] border-strong px-1.5 text-11 text-tertiary"
    >
      <Timer className="size-3" />
      {formatDuration(total)}
    </span>
  );
});
