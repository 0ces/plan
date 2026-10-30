/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { InitiativesService } from "../services/initiatives.service";
import type { TInitiativeLink } from "../services/initiatives.service";
import type { TInitiative, TInitiativeInput } from "../types";

export const initiativesService = new InitiativesService();

/** Initiatives per workspace, and whether the workspace has them switched on. */
export class InitiativesStore {
  enabled: Record<string, boolean | undefined> = {};
  bySlug: Record<string, TInitiative[] | undefined> = {};
  byId: Record<string, TInitiative> = {};

  constructor() {
    makeObservable(this, {
      enabled: observable,
      bySlug: observable,
      byId: observable,
      fetchEnabled: action,
      setEnabled: action,
      fetchAll: action,
      fetchOne: action,
    });
  }

  fetchEnabled = async (slug: string) => {
    const features = await initiativesService.getFeatures(slug);
    runInAction(() => (this.enabled[slug] = !!features.initiatives));
  };

  setEnabled = async (slug: string, value: boolean) => {
    const features = await initiativesService.setFeatures(slug, { initiatives: value });
    runInAction(() => (this.enabled[slug] = !!features.initiatives));
  };

  fetchAll = async (slug: string) => {
    const list = await initiativesService.list(slug);
    runInAction(() => {
      this.bySlug[slug] = list;
      for (const i of list) this.byId[i.id] = i;
    });
  };

  fetchOne = async (slug: string, id: string) => {
    const one = await initiativesService.retrieve(slug, id);
    runInAction(() => (this.byId[id] = one));
    return one;
  };

  create = async (slug: string, data: TInitiativeInput) => {
    const made = await initiativesService.create(slug, data);
    await this.fetchAll(slug);
    return made;
  };

  update = async (slug: string, id: string, data: TInitiativeInput) => {
    const before = this.byId[id];
    if (before) runInAction(() => (this.byId[id] = { ...before, ...data }));
    try {
      const saved = await initiativesService.update(slug, id, data);
      runInAction(() => (this.byId[id] = saved));
    } catch (error) {
      if (before) runInAction(() => (this.byId[id] = before));
      throw error;
    }
  };

  remove = async (slug: string, id: string) => {
    await initiativesService.remove(slug, id);
    await this.fetchAll(slug);
  };

  link = async (slug: string, id: string, kind: TInitiativeLink, ids: string[], add: boolean) => {
    if (add) await initiativesService.link(slug, id, kind, ids);
    else await initiativesService.unlink(slug, id, kind, ids);
    await this.fetchOne(slug, id);
  };
}

export const initiativesStore = new InitiativesStore();
