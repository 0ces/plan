/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TWorkLog, TWorkLogInput, TWorkLogRange } from "../types";

export class WorkLogsService extends APIService {
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

  list(slug: string, projectId: string, issueId: string): Promise<TWorkLog[]> {
    return this.run(this.get(`${this.base(slug, projectId)}/work-items/${issueId}/worklogs/`));
  }

  create(slug: string, projectId: string, issueId: string, data: TWorkLogInput): Promise<TWorkLog> {
    return this.run(this.post(`${this.base(slug, projectId)}/work-items/${issueId}/worklogs/`, data));
  }

  update(
    slug: string,
    projectId: string,
    issueId: string,
    id: string,
    data: Partial<TWorkLogInput>
  ): Promise<TWorkLog> {
    return this.run(this.patch(`${this.base(slug, projectId)}/work-items/${issueId}/worklogs/${id}/`, data));
  }

  remove(slug: string, projectId: string, issueId: string, id: string): Promise<void> {
    return this.run(this.delete(`${this.base(slug, projectId)}/work-items/${issueId}/worklogs/${id}/`));
  }

  summary(slug: string, projectId: string): Promise<{ work_item_id: string; duration: number }[]> {
    return this.run(this.get(`${this.base(slug, projectId)}/worklogs/summary/`));
  }

  range(slug: string, projectId: string, from: string, to: string): Promise<TWorkLogRange> {
    return this.run(this.get(`${this.base(slug, projectId)}/worklogs/`, { params: { from, to } }));
  }
}
