/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "@plane/types";

export type TWorkItemType = {
  id: string;
  name: string;
  description: string;
  logo_props: TLogoProps | Record<string, never>;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  level: number;
  project_ids: string[];
};

export type TWorkItemTypeInput = Partial<
  Pick<TWorkItemType, "name" | "description" | "logo_props" | "is_active" | "is_epic" | "is_default">
>;

export type TEpicProgress = {
  backlog_issues: number;
  unstarted_issues: number;
  started_issues: number;
  completed_issues: number;
  cancelled_issues: number;
  overdue_issues: number;
  total_issues: number;
};

export type TEpic = {
  id: string;
  name: string;
  sequence_id: number;
  project_id: string;
  type_id: string;
  state_id: string | null;
  priority: string | null;
  start_date: string | null;
  target_date: string | null;
  progress: TEpicProgress;
};
