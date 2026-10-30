/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Live updates: listens to the live server's /oces/events socket and reloads whatever
// changed through the existing stores, so the API keeps doing the permission checks.
// Events carry ids only (see apps/api/plane/oces/live.py).

import { toJS } from "mobx";
import { LIVE_BASE_PATH, LIVE_BASE_URL } from "@plane/constants";
import type { TIssue } from "@plane/types";
import { rootStore } from "@/lib/store-context";
import { EIssueGroupedAction } from "@/store/issue/helpers/base-issues.store";
import { IssueService } from "@/services/issue";
import { epicsStore } from "@oces/store/epics.store";
import { initiativesStore } from "@oces/store/initiatives.store";
import { propertiesStore } from "@oces/store/properties.store";

export type LiveEvent = {
  project_id?: string | null;
  issue_id?: string | null;
  cycle_id?: string | null;
  module_id?: string | null;
  route?: string | null;
  action: string;
};

const DEBOUNCE_MS = 400;
const TYPING_RECHECK_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

type ListTarget = {
  /** reload the first page(s) of the list the user is looking at */
  refetch: () => Promise<unknown> | undefined;
  /** per-item patching; undefined when membership depends on saved filters (views, archives) */
  patch?: {
    store: {
      updateIssueList: (
        issue?: TIssue,
        before?: TIssue,
        action?: EIssueGroupedAction.ADD | EIssueGroupedAction.DELETE
      ) => void;
      removeIssueFromList: (id: string) => void;
    };
    belongs: (issue: TIssue) => boolean;
  };
};

/** The issue list on screen, if any. */
export const currentList = (slug: string): ListTarget | undefined => {
  const { router, issue } = rootStore;
  const projectId = router.projectId;
  const path = window.location.pathname;
  if (!projectId) return undefined;
  if (path.includes("/archives/issues")) {
    return { refetch: () => issue.archivedIssues.fetchIssuesWithExistingPagination(slug, projectId, "mutation") };
  }
  if (router.cycleId) {
    const cycleId = router.cycleId;
    return {
      refetch: () => issue.cycleIssues.fetchIssuesWithExistingPagination(slug, projectId, "mutation", cycleId),
      patch: { store: issue.cycleIssues as never, belongs: (i) => i.cycle_id === cycleId },
    };
  }
  if (router.moduleId) {
    const moduleId = router.moduleId;
    return {
      refetch: () => issue.moduleIssues.fetchIssuesWithExistingPagination(slug, projectId, "mutation", moduleId),
      patch: { store: issue.moduleIssues as never, belongs: (i) => !!i.module_ids?.includes(moduleId) },
    };
  }
  if (router.viewId) {
    const viewId = router.viewId;
    return {
      refetch: () => issue.projectViewIssues.fetchIssuesWithExistingPagination(slug, projectId, viewId, "mutation"),
    };
  }
  if (/\/projects\/[^/]+\/issues\/?$/.test(path)) {
    return {
      refetch: () => issue.projectIssues.fetchIssuesWithExistingPagination(slug, projectId, "mutation"),
      patch: { store: issue.projectIssues as never, belongs: (i) => i.project_id === projectId && !i.is_draft },
    };
  }
  return undefined;
};

/** Whether this work item is open in the peek panel or full page. */
const isOpen = (issueId: string, issue?: TIssue) => {
  const { issueDetail } = rootStore.issue;
  if (issueDetail.peekIssue?.issueId === issueId) return true;
  const workItem = rootStore.router.query?.workItem?.toString();
  if (!workItem || !issue) return false;
  const identifier = rootStore.projectRoot.project.getProjectById(issue.project_id ?? "")?.identifier;
  return `${identifier}-${issue.sequence_id}`.toUpperCase() === workItem.toUpperCase();
};

/** Don't swap content under someone who is typing; wait until they stop. */
const isTyping = () => {
  const el = document.activeElement;
  return !!el && (el.closest(".ProseMirror") !== null || el.tagName === "TEXTAREA");
};

export class LiveEvents {
  private ws: WebSocket | undefined;
  private retries = 0;
  private stopped = false;
  private connectedBefore = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private pending: LiveEvent[] = [];
  private issueService = new IssueService();

  constructor(private slug: string) {}

  start() {
    this.stopped = false;
    this.connect();
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.timer);
    this.ws?.close(1000);
  }

  private url() {
    const url = new URL(LIVE_BASE_URL?.trim() || window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${LIVE_BASE_PATH}/oces/events`;
    url.searchParams.set("workspaceSlug", this.slug);
    return url.toString();
  }

  private connect() {
    const ws = new WebSocket(this.url());
    this.ws = ws;
    ws.addEventListener("message", (msg) => {
      let event: LiveEvent;
      try {
        event = JSON.parse(String(msg.data)) as LiveEvent;
      } catch {
        return;
      }
      if (event.action === "ready") {
        this.retries = 0;
        // after a reconnect we may have missed events: reload the current view once
        if (this.connectedBefore) void currentList(this.slug)?.refetch();
        this.connectedBefore = true;
        return;
      }
      this.pending.push(event);
      this.schedule(DEBOUNCE_MS);
    });
    ws.addEventListener("close", (e) => {
      if (this.stopped || this.ws !== ws) return;
      // 4403: not a member (any more); retry slowly in case that changes
      const wait = e.code === 4403 ? MAX_BACKOFF_MS * 2 : Math.min(MAX_BACKOFF_MS, 1000 * 2 ** this.retries++);
      this.timer = setTimeout(() => this.connect(), wait);
    });
  }

  private schedule(ms: number) {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.flush(), ms);
  }

  private async flush() {
    if (isTyping()) return this.schedule(TYPING_RECHECK_MS);
    const events = this.pending;
    this.pending = [];
    await applyEvents(this.slug, events, this.issueService).catch(() => undefined);
  }
}

export const applyEvents = async (slug: string, events: LiveEvent[], issueService: IssueService) => {
  const { router, state, label, cycle, module } = rootStore;
  const projectId = router.projectId;
  const list = currentList(slug);
  let refetchList = false;
  const touched = new Map<string, LiveEvent>(); // issue id -> latest event
  const projectEvents = events.filter((e) => e.project_id && e.project_id === projectId);

  for (const e of events) {
    if (e.issue_id && e.project_id) touched.set(e.issue_id, e);
    else if (e.project_id === projectId) refetchList = true; // bulk changes, cycle/module membership…
  }

  // initiatives pages: reload the list, or the open initiative (its progress depends on any work item)
  const initiativePage = window.location.pathname.match(/\/initiatives\/?([0-9a-f-]{36})?/);
  if (initiativePage && events.length) {
    if (initiativePage[1]) void initiativesStore.fetchOne(slug, initiativePage[1]).catch(() => undefined);
    else void initiativesStore.fetchAll(slug).catch(() => undefined);
  }

  // project-level lists used across the UI
  const routes = new Set(projectEvents.filter((e) => !e.issue_id).map((e) => e.route ?? ""));
  const has = (word: string) => [...routes].some((r) => r.includes(word));
  if (projectId) {
    if (has("state")) void state.fetchProjectStates(slug, projectId);
    if (has("label")) void label.fetchProjectLabels(slug, projectId);
    if (has("cycle")) {
      void cycle.fetchAllCycles(slug, projectId);
      if (router.cycleId) void cycle.fetchCycleDetails(slug, projectId, router.cycleId);
    }
    if (has("module")) {
      void module.fetchModules(slug, projectId);
      if (router.moduleId) void module.fetchModuleDetails(slug, projectId, router.moduleId);
    }
    if (projectEvents.length && window.location.pathname.includes("/epics")) void epicsStore.fetch(slug, projectId);
  }

  const needsRefetch = await Promise.all(
    [...touched].map(([issueId, e]) => applyIssueEvent(slug, issueId, e, list, issueService))
  );
  if (needsRefetch.includes(true)) refetchList = true;

  if (refetchList) await list?.refetch();
};

/** Reload one work item and move it in the list on screen. Returns true when the list must be reloaded instead. */
const applyIssueEvent = async (
  slug: string,
  issueId: string,
  e: LiveEvent,
  list: ListTarget | undefined,
  issueService: IssueService
): Promise<boolean> => {
  const { router, issue } = rootStore;
  const projectId = router.projectId;
  const projectOfIssue = e.project_id as string;
  const known = issue.issues.getIssueById(issueId);
  const before = known ? (toJS(known) as TIssue) : undefined;
  const open = isOpen(issueId, known);

  if (e.action === "activity") {
    if (open) void issue.issueDetail.fetchActivities(slug, projectOfIssue, issueId);
    return false;
  }
  // custom property values: the API writes their history itself, so no "activity" event follows
  if (open && e.route?.includes("propert")) {
    void propertiesStore.fetchValues(slug, projectOfIssue, issueId).catch(() => undefined);
    void issue.issueDetail.fetchActivities(slug, projectOfIssue, issueId);
    return false;
  }
  // only bother with items on screen or in the project being viewed
  if (!open && !known && projectOfIssue !== projectId) return false;

  let after: TIssue | undefined;
  try {
    if (open) await issue.issueDetail.fetchIssue(slug, projectOfIssue, issueId);
    else issue.issues.addIssue([await issueService.retrieve(slug, projectOfIssue, issueId)]);
    after = issue.issues.getIssueById(issueId);
  } catch {
    after = undefined; // deleted, archived or no longer visible
  }

  if (!list || projectOfIssue !== projectId) return false;
  if (!list.patch) return true;
  const { store, belongs } = list.patch;
  const wasIn = !!before && belongs(before);
  const isIn = !!after && belongs(after) && !after.archived_at;
  if (wasIn && isIn) store.updateIssueList(after, before);
  // shortcut: a new item joins the list even if display filters would hide it (same as upstream quick-add)
  else if (isIn) store.updateIssueList(after, undefined, EIssueGroupedAction.ADD);
  else if (wasIn) store.removeIssueFromList(issueId);
  return false;
};
