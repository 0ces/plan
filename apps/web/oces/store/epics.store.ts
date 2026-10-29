/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction } from "mobx";
import { WorkItemTypesService } from "../services/work-item-types.service";
import type { TEpic } from "../types";

const service = new WorkItemTypesService();

/** Epics per project with child progress. */
class EpicsStore {
  epicsByProject: Record<string, TEpic[] | undefined> = {};

  constructor() {
    makeObservable(this, { epicsByProject: observable });
  }

  fetch = async (workspaceSlug: string, projectId: string) => {
    const epics = await service.listEpics(workspaceSlug, projectId);
    runInAction(() => {
      this.epicsByProject[projectId] = epics;
    });
  };
}

export const epicsStore = new EpicsStore();
