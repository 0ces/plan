/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { X } from "lucide-react";
import { API_BASE_URL, EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useUserPermissions } from "@/hooks/store/user";

// shortcut: same banner lives in apps/admin/oces/version-banner.tsx; move to a package if a third app needs it
type TVersion = {
  current: string;
  latest: string | null;
  update_available: boolean;
  latest_url: string | null;
  upstream_latest: string | null;
  upstream_update_available: boolean;
  upstream_latest_url: string | null;
};
type TNotice = { id: string; text: string; url: string | null };

const DISMISSED = "oces-version-dismissed";

function readDismissed(): string[] {
  try {
    return JSON.parse(localStorage.getItem(DISMISSED) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function notices(v: TVersion): TNotice[] {
  const out: TNotice[] = [];
  if (v.update_available && v.latest)
    out.push({ id: v.latest, text: `${v.latest} available (running ${v.current})`, url: v.latest_url });
  if (v.upstream_update_available && v.upstream_latest)
    out.push({
      id: `plane-${v.upstream_latest}`,
      text: `Plane ${v.upstream_latest} released`,
      url: v.upstream_latest_url,
    });
  return out;
}

/** New fork / Plane release notices, for workspace admins only. */
export const OcesVersionBanner = observer(function OcesVersionBanner() {
  const { workspaceSlug } = useParams();
  const { allowPermissions } = useUserPermissions();
  const isAdmin =
    !!workspaceSlug && allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);
  const [version, setVersion] = useState<TVersion | null>(null);
  const [dismissed, setDismissed] = useState<string[]>(readDismissed);

  useEffect(() => {
    if (!isAdmin) return;
    fetch(`${API_BASE_URL}/api/oces/version/`, { credentials: "include" })
      .then((r) => (r.ok ? (r.json() as Promise<TVersion>) : null))
      .then(setVersion)
      .catch(() => undefined);
  }, [isAdmin]);

  if (!isAdmin || !version) return null;
  const shown = notices(version).filter((n) => !dismissed.includes(n.id));
  if (!shown.length) return null;

  const dismiss = (id: string) => {
    const next = [...dismissed, id];
    setDismissed(next);
    try {
      localStorage.setItem(DISMISSED, JSON.stringify(next));
    } catch {
      // private mode: dismissed for this visit only
    }
  };

  return (
    <div className="flex flex-col gap-px border-b border-subtle">
      {shown.map((n) => (
        <div key={n.id} className="flex items-center gap-3 bg-accent-subtle px-4 py-1.5 text-12 text-accent-primary">
          <span className="flex-1">{n.text}</span>
          {n.url && (
            <a href={n.url} target="_blank" rel="noopener noreferrer" className="font-medium underline">
              Release notes
            </a>
          )}
          <button type="button" aria-label={`Dismiss: ${n.text}`} onClick={() => dismiss(n.id)} className="p-0.5">
            <X className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
});
