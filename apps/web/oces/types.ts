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

// ---------------------------------------------------------------- custom properties

export type TPropertyType = "TEXT" | "DECIMAL" | "BOOLEAN" | "DATETIME" | "OPTION" | "URL" | "EMAIL" | "RELATION";
export type TRelationType = "USER" | "ISSUE" | "RICH_TEXT" | "MODULE";

export type TPropertyOption = {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  logo_props: { in_use?: string; color?: string } & Record<string, unknown>;
  is_active: boolean;
  is_default: boolean;
};

export type TProperty = {
  id: string;
  display_name: string;
  description: string;
  property_type: TPropertyType;
  relation_type: TRelationType | null;
  settings: { display_format: string } | null;
  is_required: boolean;
  is_multi: boolean;
  is_active: boolean;
  default_value: string[];
  sort_order: number;
  project: string | null;
  issue_type_ids: string[];
  options: TPropertyOption[];
};

export type TPropertyInput = Partial<
  Pick<
    TProperty,
    | "display_name"
    | "description"
    | "property_type"
    | "relation_type"
    | "settings"
    | "is_required"
    | "is_multi"
    | "is_active"
    | "default_value"
    | "sort_order"
  >
> & { options?: { name: string; is_default?: boolean; color?: string }[] };

/** One work item's values: property id -> value (a list for multi-value properties). */
export type TPropertyValue = string | number | boolean | string[] | null;
export type TPropertyValues = Record<string, TPropertyValue>;

// ---------------------------------------------------------------- initiatives

export type TInitiativeState = "DRAFT" | "PLANNED" | "ACTIVE" | "COMPLETED" | "CLOSED";

export type TInitiative = {
  id: string;
  name: string;
  description_html: string;
  description_stripped: string;
  start_date: string | null;
  end_date: string | null;
  state: TInitiativeState;
  lead: string | null;
  logo_props: Record<string, unknown>;
  label_ids: string[];
  project_ids: string[];
  epic_ids: string[];
  work_item_ids: string[];
  progress: TEpicProgress;
  created_by: string | null;
};

export type TInitiativeInput = Partial<
  Pick<TInitiative, "name" | "description_html" | "start_date" | "end_date" | "state" | "lead">
>;

/** Linked work item as the internal API returns it (upstream work item serializer). */
export type TLinkedWorkItem = {
  id: string;
  name: string;
  sequence_id: number;
  project: string;
  state: string;
  priority: string;
};

// ---------------------------------------------------------------- time logs

export type TWorkLog = {
  id: string;
  work_item_id: string;
  project_id: string;
  duration: number; // minutes
  description: string;
  logged_at: string; // YYYY-MM-DD
  logged_by: string;
  created_at: string;
  work_item?: { id: string; sequence_id: number; name: string };
};

export type TWorkLogInput = { duration: number; description?: string; logged_at?: string };

export type TWorkLogRange = { from: string; to: string; results: TWorkLog[] };

// ---------------------------------------------------------------- Bitbucket

export type TPullRequest = {
  id: string;
  provider: string;
  repository: string;
  number: number;
  title: string;
  url: string;
  state: "OPEN" | "MERGED" | "DECLINED" | "SUPERSEDED" | string;
  author: string;
  source_branch: string;
  target_branch: string;
  updated_at: string | null;
};

export type TBitbucketSettings =
  | { enabled: false }
  | { enabled: true; webhook_url: string; secret: string; last_event_at: string | null; pull_requests: number };
