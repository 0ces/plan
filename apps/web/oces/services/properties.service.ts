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

  private base(slug: string, projectId: string) {
    return `/api/workspaces/${slug}/projects/${projectId}/oces`;
  }

  private async run<T>(request: Promise<{ data: T }>): Promise<T> {
    try {
      return (await request).data;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }

  listForType(slug: string, projectId: string, typeId: string): Promise<TProperty[]> {
    return this.run(this.get(`${this.base(slug, projectId)}/work-item-types/${typeId}/work-item-properties/`));
  }

  create(slug: string, projectId: string, typeId: string, data: TPropertyInput): Promise<TProperty> {
    return this.run(this.post(`${this.base(slug, projectId)}/work-item-types/${typeId}/work-item-properties/`, data));
  }

  update(slug: string, projectId: string, propertyId: string, data: TPropertyInput): Promise<TProperty> {
    return this.run(this.patch(`${this.base(slug, projectId)}/work-item-properties/${propertyId}/`, data));
  }

  remove(slug: string, projectId: string, propertyId: string): Promise<void> {
    return this.run(this.delete(`${this.base(slug, projectId)}/work-item-properties/${propertyId}/`));
  }

  createOption(slug: string, projectId: string, propertyId: string, data: Partial<TPropertyOption>) {
    return this.run<TPropertyOption>(
      this.post(`${this.base(slug, projectId)}/work-item-properties/${propertyId}/options/`, data)
    );
  }

  updateOption(slug: string, projectId: string, propertyId: string, optionId: string, data: Partial<TPropertyOption>) {
    return this.run<TPropertyOption>(
      this.patch(`${this.base(slug, projectId)}/work-item-properties/${propertyId}/options/${optionId}/`, data)
    );
  }

  removeOption(slug: string, projectId: string, propertyId: string, optionId: string): Promise<void> {
    return this.run(
      this.delete(`${this.base(slug, projectId)}/work-item-properties/${propertyId}/options/${optionId}/`)
    );
  }

  values(slug: string, projectId: string, issueId: string): Promise<TPropertyValues> {
    return this.run(this.get(`${this.base(slug, projectId)}/work-items/${issueId}/property-values/`));
  }

  setValue(slug: string, projectId: string, issueId: string, propertyId: string, value: unknown) {
    return this.run(
      this.post(`${this.base(slug, projectId)}/work-items/${issueId}/work-item-properties/${propertyId}/values/`, {
        value,
      })
    );
  }

  clearValue(slug: string, projectId: string, issueId: string, propertyId: string): Promise<void> {
    return this.run(
      this.delete(`${this.base(slug, projectId)}/work-items/${issueId}/work-item-properties/${propertyId}/values/`)
    );
  }
}
