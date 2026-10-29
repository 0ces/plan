/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TEpic, TEpicProgress, TWorkItemType, TWorkItemTypeInput } from "../types";

export class WorkItemTypesService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string, projectId: string) {
    return `/api/workspaces/${workspaceSlug}/projects/${projectId}/oces`;
  }

  private async run<T>(request: Promise<{ data: T }>): Promise<T> {
    try {
      return (await request).data;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }

  getFeatures(workspaceSlug: string, projectId: string): Promise<Record<string, boolean>> {
    return this.run(this.get(`${this.base(workspaceSlug, projectId)}/features/`));
  }

  setFeatures(
    workspaceSlug: string,
    projectId: string,
    data: Record<string, boolean>
  ): Promise<Record<string, boolean>> {
    return this.run(this.patch(`${this.base(workspaceSlug, projectId)}/features/`, data));
  }

  list(workspaceSlug: string, projectId: string): Promise<TWorkItemType[]> {
    return this.run(this.get(`${this.base(workspaceSlug, projectId)}/work-item-types/`));
  }

  create(workspaceSlug: string, projectId: string, data: TWorkItemTypeInput): Promise<TWorkItemType> {
    return this.run(this.post(`${this.base(workspaceSlug, projectId)}/work-item-types/`, data));
  }

  update(workspaceSlug: string, projectId: string, typeId: string, data: TWorkItemTypeInput): Promise<TWorkItemType> {
    return this.run(this.patch(`${this.base(workspaceSlug, projectId)}/work-item-types/${typeId}/`, data));
  }

  remove(workspaceSlug: string, projectId: string, typeId: string): Promise<void> {
    return this.run(this.delete(`${this.base(workspaceSlug, projectId)}/work-item-types/${typeId}/`));
  }

  listEpics(workspaceSlug: string, projectId: string): Promise<TEpic[]> {
    return this.run(this.get(`${this.base(workspaceSlug, projectId)}/epics/`));
  }

  epicProgress(workspaceSlug: string, projectId: string, epicId: string): Promise<TEpicProgress> {
    return this.run(this.get(`${this.base(workspaceSlug, projectId)}/epics/${epicId}/progress/`));
  }
}
