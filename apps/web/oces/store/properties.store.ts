/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { PropertiesService } from "../services/properties.service";
import type { TProperty, TPropertyInput, TPropertyOption, TPropertyValue, TPropertyValues } from "../types";

const service = new PropertiesService();

export const isRichText = (p: TProperty) => p.property_type === "RELATION" && p.relation_type === "RICH_TEXT";

export const isEmptyValue = (v: TPropertyValue | undefined) =>
  v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);

/** What the values endpoint expects for this property. */
export const toApiValue = (p: TProperty, v: TPropertyValue) => (isRichText(p) ? { description_html: v } : v);

/** Default values a new work item starts with, as the server applies them. */
export const defaultValueOf = (p: TProperty): TPropertyValue | undefined => {
  if (p.property_type === "OPTION") {
    const ids = p.options.filter((o) => o.is_default && o.is_active).map((o) => o.id);
    if (!ids.length) return undefined;
    return p.is_multi ? ids : ids[0];
  }
  const first = p.default_value?.[0];
  if (first === undefined || isRichText(p)) return undefined;
  if (p.property_type === "DECIMAL") return Number.isNaN(Number(first)) ? undefined : Number(first);
  if (p.property_type === "BOOLEAN") return first.toLowerCase() === "true";
  return p.is_multi ? [first] : first;
};

/** Properties per work item type, and values per work item. One shared instance, like the types store. */
export class PropertiesStore {
  byType: Record<string, TProperty[]> = {};
  valuesByIssue: Record<string, TPropertyValues> = {};
  private loading: Record<string, Promise<void> | undefined> = {};

  constructor() {
    makeObservable(this, {
      byType: observable,
      valuesByIssue: observable,
      fetchForType: action,
      fetchValues: action,
      setValue: action,
    });
  }

  getForType = (typeId: string | null | undefined): TProperty[] => (typeId ? (this.byType[typeId] ?? []) : []);

  getActiveForType = (typeId: string | null | undefined) => this.getForType(typeId).filter((p) => p.is_active);

  fetchForType = (slug: string, projectId: string, typeId: string, force = false): Promise<void> => {
    if (!force && this.loading[typeId]) return this.loading[typeId]!;
    const load = service.listForType(slug, projectId, typeId).then((list) =>
      runInAction(() => {
        this.byType[typeId] = list;
      })
    );
    this.loading[typeId] = load.catch(() => {
      this.loading[typeId] = undefined;
    });
    return this.loading[typeId]!;
  };

  fetchValues = async (slug: string, projectId: string, issueId: string) => {
    const values = await service.values(slug, projectId, issueId);
    runInAction(() => {
      this.valuesByIssue[issueId] = values;
    });
  };

  /** Save one value; an empty value clears it. Rolls back on error. */
  setValue = async (slug: string, projectId: string, issueId: string, property: TProperty, value: TPropertyValue) => {
    const before = this.valuesByIssue[issueId]?.[property.id];
    runInAction(() => {
      this.valuesByIssue[issueId] = { ...this.valuesByIssue[issueId], [property.id]: value };
    });
    try {
      if (isEmptyValue(value)) await service.clearValue(slug, projectId, issueId, property.id);
      else await service.setValue(slug, projectId, issueId, property.id, toApiValue(property, value));
    } catch (error) {
      runInAction(() => {
        this.valuesByIssue[issueId] = { ...this.valuesByIssue[issueId], [property.id]: before ?? null };
      });
      throw error;
    }
  };

  /** After creating a work item: save every filled value from the create form. */
  saveAll = async (slug: string, projectId: string, issueId: string, typeId: string, values: TPropertyValues) => {
    const before = this.valuesByIssue[issueId] ?? {};
    await Promise.all(
      this.getActiveForType(typeId).map((p) => {
        const v = values[p.id];
        if (!isEmptyValue(v)) return service.setValue(slug, projectId, issueId, p.id, toApiValue(p, v));
        // emptied in the form: also drop a default the server added on create
        if (!isEmptyValue(before[p.id]) || defaultValueOf(p) !== undefined)
          return service.clearValue(slug, projectId, issueId, p.id).catch(() => undefined);
        return undefined;
      })
    );
    await this.fetchValues(slug, projectId, issueId);
  };

  // definitions (settings page)
  create = async (slug: string, projectId: string, typeId: string, data: TPropertyInput) => {
    await service.create(slug, projectId, typeId, data);
    await this.fetchForType(slug, projectId, typeId, true);
  };

  update = async (slug: string, projectId: string, typeId: string, propertyId: string, data: TPropertyInput) => {
    await service.update(slug, projectId, propertyId, data);
    await this.fetchForType(slug, projectId, typeId, true);
  };

  remove = async (slug: string, projectId: string, typeId: string, propertyId: string) => {
    await service.remove(slug, projectId, propertyId);
    await this.fetchForType(slug, projectId, typeId, true);
  };

  /** Bring the options in line with the edited list: add new, rename, delete removed. */
  syncOptions = async (
    slug: string,
    projectId: string,
    property: TProperty,
    wanted: { id?: string; name: string; is_default: boolean }[]
  ) => {
    const keep = new Set(wanted.filter((o) => o.id).map((o) => o.id));
    const removed = property.options.filter((old) => !keep.has(old.id));
    await Promise.all(removed.map((old) => service.removeOption(slug, projectId, property.id, old.id)));
    await Promise.all(
      wanted.map((o, index) => {
        const data: Partial<TPropertyOption> = {
          name: o.name,
          is_default: o.is_default,
          sort_order: (index + 1) * 10_000,
        };
        return o.id
          ? service.updateOption(slug, projectId, property.id, o.id, data)
          : service.createOption(slug, projectId, property.id, data);
      })
    );
  };
}

export const propertiesStore = new PropertiesStore();
