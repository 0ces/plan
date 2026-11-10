/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { GitPullRequest } from "lucide-react";
import { Tooltip } from "@plane/propel/tooltip";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { BitbucketService } from "../services/bitbucket.service";
import type { TPullRequest } from "../types";

const service = new BitbucketService();

const STATE_STYLE: Record<string, string> = {
  OPEN: "bg-accent-primary/15 text-accent-primary",
  MERGED: "bg-success-primary/15 text-success-primary",
  DECLINED: "bg-danger-primary/15 text-danger-primary",
};

type Props = { workspaceSlug: string; projectId: string; issueId: string };

/** Bitbucket pull requests that mention this work item. Hidden when there are none. */
export function WorkItemPullRequests({ workspaceSlug, projectId, issueId }: Props) {
  const [prs, setPrs] = useState<TPullRequest[]>([]);

  useEffect(() => {
    let alive = true;
    service
      .pullRequests(workspaceSlug, projectId, issueId)
      .then((list) => alive && setPrs(list))
      .catch(() => alive && setPrs([]));
    return () => {
      alive = false;
    };
  }, [workspaceSlug, projectId, issueId]);

  if (!prs.length) return null;

  return (
    <SidebarPropertyListItem
      icon={GitPullRequest}
      label="Pull requests"
      childrenClassName="flex-col items-start gap-1 py-1"
    >
      {prs.map((pr) => (
        <Tooltip
          key={pr.id}
          tooltipHeading={`${pr.repository} #${pr.number}`}
          tooltipContent={`${pr.source_branch} → ${pr.target_branch}${pr.author ? ` · ${pr.author}` : ""}`}
        >
          <a
            href={pr.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full min-w-0 items-center gap-1.5 rounded-sm px-1 py-0.5 text-body-xs-regular text-secondary hover:bg-layer-transparent-hover"
          >
            <span
              className={`shrink-0 rounded-sm px-1 text-caption-sm-medium ${STATE_STYLE[pr.state] ?? "bg-layer-1 text-tertiary"}`}
            >
              {pr.state.toLowerCase()}
            </span>
            <span className="shrink-0 text-tertiary">#{pr.number}</span>
            <span className="truncate">{pr.title}</span>
          </a>
        </Tooltip>
      ))}
    </SidebarPropertyListItem>
  );
}
