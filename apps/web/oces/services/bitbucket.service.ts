/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TBitbucketSettings, TPullRequest } from "../types";

export class BitbucketService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private async run<T>(request: Promise<{ data: T }>): Promise<T> {
    try {
      return (await request).data;
    } catch (error: any) {
      throw error?.response?.data ?? error;
    }
  }

  settings(slug: string): Promise<TBitbucketSettings> {
    return this.run(this.get(`/api/workspaces/${slug}/oces/bitbucket/`));
  }

  /** Turn on, or replace the secret. */
  newSecret(slug: string): Promise<TBitbucketSettings> {
    return this.run(this.post(`/api/workspaces/${slug}/oces/bitbucket/`, {}));
  }

  disable(slug: string): Promise<void> {
    return this.run(this.delete(`/api/workspaces/${slug}/oces/bitbucket/`));
  }

  pullRequests(slug: string, projectId: string, issueId: string): Promise<TPullRequest[]> {
    return this.run(
      this.get(`/api/workspaces/${slug}/projects/${projectId}/oces/work-items/${issueId}/pull-requests/`)
    );
  }
}
