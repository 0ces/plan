/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TProperty, TPropertyInput, TPropertyOption, TPropertyValues } from "../types";

/** Custom properties through the internal API (session cookie). */
export class PropertiesService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  protected base(slug: string, projectId: string) {
    return `/api/workspaces/${slug}/projects/${projectId}/oces`;
  }

  /** Definitions of one type (list/create); `scopeId` is the type id. */
  protected defs(slug: string, projectId: string, scopeId: string) {
    return `${this.base(slug, projectId)}/work-item-types/${scopeId}/work-item-properties/`;
  }

  protected def(slug: string, projectId: string, propertyId: string) {
    return `${this.base(slug, projectId)}/work-item-properties/${propertyId}/`;
  }

  protected allValues(slug: string, projectId: string, ownerId: string) {
    return `${this.base(slug, projectId)}/work-items/${ownerId}/property-values/`;
  }

  protected value(slug: string, projectId: string, ownerId: string, propertyId: string) {
    return `${this.base(slug, projectId)}/work-items/${ownerId}/work-item-properties/${propertyId}/values/`;
  }

  protected async run<T>(request: Promise<{ data: T }>): Promise<T> {
    try {
      return (await request).data;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }

  listForType(slug: string, projectId: string, typeId: string): Promise<TProperty[]> {
    return this.run(this.get(this.defs(slug, projectId, typeId)));
  }

  create(slug: string, projectId: string, typeId: string, data: TPropertyInput): Promise<TProperty> {
    return this.run(this.post(this.defs(slug, projectId, typeId), data));
  }

  update(slug: string, projectId: string, propertyId: string, data: TPropertyInput): Promise<TProperty> {
    return this.run(this.patch(this.def(slug, projectId, propertyId), data));
  }

  remove(slug: string, projectId: string, propertyId: string): Promise<void> {
    return this.run(this.delete(this.def(slug, projectId, propertyId)));
  }

  createOption(slug: string, projectId: string, propertyId: string, data: Partial<TPropertyOption>) {
    return this.run<TPropertyOption>(this.post(`${this.def(slug, projectId, propertyId)}options/`, data));
  }

  updateOption(slug: string, projectId: string, propertyId: string, optionId: string, data: Partial<TPropertyOption>) {
    return this.run<TPropertyOption>(this.patch(`${this.def(slug, projectId, propertyId)}options/${optionId}/`, data));
  }

  removeOption(slug: string, projectId: string, propertyId: string, optionId: string): Promise<void> {
    return this.run(this.delete(`${this.def(slug, projectId, propertyId)}options/${optionId}/`));
  }

  values(slug: string, projectId: string, issueId: string): Promise<TPropertyValues> {
    return this.run(this.get(this.allValues(slug, projectId, issueId)));
  }

  setValue(slug: string, projectId: string, issueId: string, propertyId: string, value: unknown) {
    return this.run(this.post(this.value(slug, projectId, issueId, propertyId), { value }));
  }

  clearValue(slug: string, projectId: string, issueId: string, propertyId: string): Promise<void> {
    return this.run(this.delete(this.value(slug, projectId, issueId, propertyId)));
  }
}

/** Module properties: same calls, module paths. The scope id is the project id (one set per project). */
export class ModulePropertiesService extends PropertiesService {
  protected defs(slug: string, projectId: string) {
    return `${this.base(slug, projectId)}/module-properties/`;
  }

  protected def(slug: string, projectId: string, propertyId: string) {
    return `${this.base(slug, projectId)}/module-properties/${propertyId}/`;
  }

  protected allValues(slug: string, projectId: string, moduleId: string) {
    return `${this.base(slug, projectId)}/modules/${moduleId}/module-property-values/`;
  }

  protected value(slug: string, projectId: string, moduleId: string, propertyId: string) {
    return `${this.base(slug, projectId)}/modules/${moduleId}/module-properties/${propertyId}/values/`;
  }

  async values(slug: string, projectId: string, moduleId: string): Promise<TPropertyValues> {
    const out = await this.run<{ values: TPropertyValues }>(this.get(this.allValues(slug, projectId, moduleId)));
    return out.values;
  }

  /** {module_id: {property_id: value}} for the module list. */
  projectValues(slug: string, projectId: string): Promise<Record<string, TPropertyValues>> {
    return this.run(this.get(`${this.base(slug, projectId)}/module-property-values/`));
  }
}
