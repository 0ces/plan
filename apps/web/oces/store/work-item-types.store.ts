/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { WorkItemTypesService } from "../services/work-item-types.service";
import type { TWorkItemType, TWorkItemTypeInput } from "../types";

const service = new WorkItemTypesService();

/** Work item types per project. One shared instance; not part of upstream's root store. */
export class WorkItemTypesStore {
  typesByProject: Record<string, TWorkItemType[]> = {};
  enabledByProject: Record<string, boolean> = {};
  private loading: Record<string, Promise<void> | undefined> = {};

  constructor() {
    makeObservable(this, {
      typesByProject: observable,
      enabledByProject: observable,
      fetch: action,
      setEnabled: action,
      create: action,
      update: action,
      remove: action,
    });
  }

  /** Loads once per project; pass force to reload. */
  fetch = (workspaceSlug: string, projectId: string, force = false): Promise<void> => {
    if (!force && this.loading[projectId]) return this.loading[projectId]!;
    const load = (async () => {
      const features = await service.getFeatures(workspaceSlug, projectId);
      const types = features.work_item_types ? await service.list(workspaceSlug, projectId) : [];
      runInAction(() => {
        this.enabledByProject[projectId] = !!features.work_item_types;
        this.typesByProject[projectId] = types;
      });
    })();
    this.loading[projectId] = load.catch(() => {
      this.loading[projectId] = undefined;
    });
    return this.loading[projectId]!;
  };

  isEnabled = (projectId: string) => !!this.enabledByProject[projectId];

  getProjectTypes = (projectId: string): TWorkItemType[] => this.typesByProject[projectId] ?? [];

  getActiveTypes = (projectId: string) => this.getProjectTypes(projectId).filter((t) => t.is_active);

  getTypeById = (typeId: string | null | undefined): TWorkItemType | undefined => {
    if (!typeId) return undefined;
    for (const types of Object.values(this.typesByProject)) {
      const found = types.find((t) => t.id === typeId);
      if (found) return found;
    }
    return undefined;
  };

  getDefaultType = (projectId: string) => this.getProjectTypes(projectId).find((t) => t.is_default);

  getEpicType = (projectId: string) => this.getProjectTypes(projectId).find((t) => t.is_epic);

  setEnabled = async (workspaceSlug: string, projectId: string, enabled: boolean) => {
    await service.setFeatures(workspaceSlug, projectId, { work_item_types: enabled });
    await this.fetch(workspaceSlug, projectId, true);
  };

  create = async (workspaceSlug: string, projectId: string, data: TWorkItemTypeInput) => {
    const created = await service.create(workspaceSlug, projectId, data);
    runInAction(() => {
      this.typesByProject[projectId] = [...this.getProjectTypes(projectId), created];
    });
    return created;
  };

  update = async (workspaceSlug: string, projectId: string, typeId: string, data: TWorkItemTypeInput) => {
    await service.update(workspaceSlug, projectId, typeId, data);
    // Reload: changing the default touches other types too.
    await this.fetch(workspaceSlug, projectId, true);
  };

  remove = async (workspaceSlug: string, projectId: string, typeId: string) => {
    await service.remove(workspaceSlug, projectId, typeId);
    runInAction(() => {
      this.typesByProject[projectId] = this.getProjectTypes(projectId).filter((t) => t.id !== typeId);
    });
  };
}

export const workItemTypesStore = new WorkItemTypesStore();
