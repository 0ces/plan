/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { WorkLogsService } from "../services/worklogs.service";
import type { TWorkLog, TWorkLogInput } from "../types";

/** "1h 30m", "1.5h", "90m", "90" (minutes), "1:30" -> minutes. null when it can't be read. */
export function parseDuration(text: string): number | null {
  const s = text.trim().toLowerCase().replace(",", ".");
  if (!s) return null;
  const clock = /^(\d+):([0-5]\d)$/.exec(s);
  if (clock) return Number(clock[1]) * 60 + Number(clock[2]);
  if (/^\d+$/.test(s)) return Number(s);
  const m = /^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?$/.exec(s);
  if (!m || (!m[1] && !m[2])) return null;
  const minutes = Math.round(Number(m[1] ?? 0) * 60) + Number(m[2] ?? 0);
  return minutes > 0 ? minutes : null;
}

/** 95 -> "1h 35m", 60 -> "1h", 20 -> "20m". */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m}m`;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** Today as YYYY-MM-DD in the browser's time zone. */
export const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export class WorkLogsStore {
  logsByIssue: Record<string, TWorkLog[]> = {};
  /** project id -> work item id -> minutes */
  totalsByProject: Record<string, Record<string, number>> = {};
  private summaryLoading: Record<string, Promise<void> | undefined> = {};
  private service = new WorkLogsService();

  constructor() {
    makeObservable(this, {
      logsByIssue: observable,
      totalsByProject: observable,
      fetchLogs: action,
      fetchSummary: action,
    });
  }

  total = (projectId: string, issueId: string) => this.totalsByProject[projectId]?.[issueId] ?? 0;

  fetchLogs = async (slug: string, projectId: string, issueId: string) => {
    const logs = await this.service.list(slug, projectId, issueId);
    runInAction(() => {
      this.logsByIssue[issueId] = logs;
      this.setTotal(projectId, issueId, logs);
    });
  };

  /** Totals for the list view: one request per project, reused by every row. */
  fetchSummary = (slug: string, projectId: string, force = false): Promise<void> => {
    if (!force && this.summaryLoading[projectId]) return this.summaryLoading[projectId]!;
    const load = this.service.summary(slug, projectId).then((rows) =>
      runInAction(() => {
        this.totalsByProject[projectId] = Object.fromEntries(rows.map((r) => [r.work_item_id, r.duration]));
      })
    );
    this.summaryLoading[projectId] = load.catch(() => {
      this.summaryLoading[projectId] = undefined;
    });
    return this.summaryLoading[projectId]!;
  };

  create = async (slug: string, projectId: string, issueId: string, data: TWorkLogInput) => {
    await this.service.create(slug, projectId, issueId, data);
    await this.fetchLogs(slug, projectId, issueId);
  };

  update = async (slug: string, projectId: string, issueId: string, id: string, data: Partial<TWorkLogInput>) => {
    await this.service.update(slug, projectId, issueId, id, data);
    await this.fetchLogs(slug, projectId, issueId);
  };

  remove = async (slug: string, projectId: string, issueId: string, id: string) => {
    await this.service.remove(slug, projectId, issueId, id);
    await this.fetchLogs(slug, projectId, issueId);
  };

  private setTotal(projectId: string, issueId: string, logs: TWorkLog[]) {
    const totals = { ...this.totalsByProject[projectId] };
    totals[issueId] = logs.reduce((sum, l) => sum + l.duration, 0);
    this.totalsByProject[projectId] = totals;
  }
}

export const workLogsStore = new WorkLogsStore();
