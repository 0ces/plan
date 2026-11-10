/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction } from "mobx";
import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

class BoardOrderService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private url = (slug: string, projectId: string) => `/api/workspaces/${slug}/projects/${projectId}/oces/board-order/`;

  async load(slug: string, projectId: string): Promise<string[]> {
    return (await this.get(this.url(slug, projectId))).data.state_ids;
  }

  async save(slug: string, projectId: string, ids: string[]): Promise<string[]> {
    try {
      return (await this.put(this.url(slug, projectId), { state_ids: ids })).data.state_ids;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }
}

/** Saved order of state columns per project. Empty = upstream's order (state group, then sequence). */
export class BoardOrderStore {
  byProject: Record<string, string[]> = {};
  private requested = new Set<string>();
  private service = new BoardOrderService();

  constructor() {
    makeObservable(this, { byProject: observable });
  }

  /** Load once per project. Safe to call while rendering: the request starts after the render. */
  ensure = (slug: string, projectId: string) => {
    if (this.requested.has(projectId)) return;
    this.requested.add(projectId);
    queueMicrotask(() => {
      this.service
        .load(slug, projectId)
        .then((ids) => runInAction(() => (this.byProject[projectId] = ids)))
        .catch(() => this.requested.delete(projectId));
    });
  };

  save = async (slug: string, projectId: string, ids: string[]) => {
    const before = this.byProject[projectId];
    runInAction(() => (this.byProject[projectId] = ids));
    try {
      await this.service.save(slug, projectId, ids);
    } catch (error) {
      runInAction(() => (this.byProject[projectId] = before ?? []));
      throw error;
    }
  };

  /** States in the saved order; states not in it (new ones) keep upstream's order after the saved ones. */
  apply = <T extends { id: string }>(projectId: string, states: T[]): T[] => {
    const order = this.byProject[projectId];
    if (!order?.length) return states;
    const rank = new Map(order.map((id, i) => [id, i]));
    const known = states.filter((s) => rank.has(s.id));
    // oxlint-disable-next-line unicorn/no-array-sort -- sorts a fresh copy (lib has no toSorted)
    known.sort((a, b) => rank.get(a.id)! - rank.get(b.id)!);
    return [...known, ...states.filter((s) => !rank.has(s.id))];
  };
}

export const boardOrderStore = new BoardOrderStore();

/** Upstream hook: order the state columns of a project board. */
export function orderStateColumns<T extends { id: string }>(
  slug: string | undefined,
  projectId: string | undefined,
  states: T[]
): T[] {
  if (!slug || !projectId) return states;
  boardOrderStore.ensure(slug, projectId);
  return boardOrderStore.apply(projectId, states);
}
