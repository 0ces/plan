/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TInitiative, TInitiativeInput, TLinkedWorkItem } from "../types";

export type TInitiativeLink = "projects" | "epics" | "work-items";
const LINK_KEY: Record<TInitiativeLink, string> = {
  projects: "project_ids",
  epics: "epic_ids",
  "work-items": "work_item_ids",
};

/** Initiatives through the internal API (session cookie). */
export class InitiativesService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(slug: string) {
    return `/api/workspaces/${slug}/oces`;
  }

  private async run<T>(request: Promise<{ data: T }>): Promise<T> {
    try {
      return (await request).data;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }

  getFeatures(slug: string): Promise<Record<string, boolean>> {
    return this.run(this.get(`${this.base(slug)}/features/`));
  }

  setFeatures(slug: string, data: Record<string, boolean>): Promise<Record<string, boolean>> {
    return this.run(this.patch(`${this.base(slug)}/features/`, data));
  }

  async list(slug: string): Promise<TInitiative[]> {
    return (await this.run<{ results: TInitiative[] }>(this.get(`${this.base(slug)}/initiatives/`))).results;
  }

  retrieve(slug: string, id: string): Promise<TInitiative> {
    return this.run(this.get(`${this.base(slug)}/initiatives/${id}/`));
  }

  create(slug: string, data: TInitiativeInput): Promise<TInitiative> {
    return this.run(this.post(`${this.base(slug)}/initiatives/`, data));
  }

  update(slug: string, id: string, data: TInitiativeInput): Promise<TInitiative> {
    return this.run(this.patch(`${this.base(slug)}/initiatives/${id}/`, data));
  }

  remove(slug: string, id: string): Promise<void> {
    return this.run(this.delete(`${this.base(slug)}/initiatives/${id}/`));
  }

  linked(slug: string, id: string, kind: "epics" | "work-items"): Promise<TLinkedWorkItem[]> {
    return this.run(this.get(`${this.base(slug)}/initiatives/${id}/${kind}/`));
  }

  link(slug: string, id: string, kind: TInitiativeLink, ids: string[]) {
    return this.run(this.post(`${this.base(slug)}/initiatives/${id}/${kind}/`, { [LINK_KEY[kind]]: ids }));
  }

  unlink(slug: string, id: string, kind: TInitiativeLink, ids: string[]) {
    return this.run(this.delete(`${this.base(slug)}/initiatives/${id}/${kind}/`, { [LINK_KEY[kind]]: ids }));
  }
}
