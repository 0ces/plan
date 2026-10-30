/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "react-router";
import { Target } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Breadcrumbs, EModalPosition, EModalWidth, Header, Input, ModalCore } from "@plane/ui";
import { renderFormattedDate } from "@plane/utils";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { useMember } from "@/hooks/store/use-member";
import { useUserPermissions } from "@/hooks/store/user";
import { initiativesStore } from "../store/initiatives.store";
import type { TInitiativeState } from "../types";
import { EpicProgressBar } from "./epic-progress-bar";

export const STATE_STYLE: Record<TInitiativeState, { label: string; className: string }> = {
  DRAFT: { label: "Draft", className: "bg-layer-3 text-secondary" },
  PLANNED: { label: "Planned", className: "bg-accent-subtle text-accent-primary" },
  ACTIVE: { label: "Active", className: "bg-warning-subtle text-warning-primary" },
  COMPLETED: { label: "Completed", className: "bg-success-subtle text-success-primary" },
  CLOSED: { label: "Closed", className: "bg-layer-3 text-tertiary" },
};

export function StateBadge({ state }: { state: TInitiativeState }) {
  const s = STATE_STYLE[state];
  return <span className={`rounded-sm px-1.5 py-0.5 text-11 font-medium ${s.className}`}>{s.label}</span>;
}

export const dateRange = (start: string | null, end: string | null) =>
  start || end ? `${start ? renderFormattedDate(start) : "…"} → ${end ? renderFormattedDate(end) : "…"}` : "";

function NewInitiativeModal({ slug, isOpen, onClose }: { slug: string; isOpen: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await initiativesStore.create(slug, { name: name.trim() });
      setName("");
      onClose();
    } catch (error: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: String(error?.name ?? "Could not create it.") });
    } finally {
      setSaving(false);
    }
  };
  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.LG}>
      <form onSubmit={submit} className="space-y-4 p-5">
        <h3 className="text-h4-medium text-secondary">New initiative</h3>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name, e.g. Launch v2"
          className="w-full"
          maxLength={255}
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={saving} disabled={!name.trim()}>
            Create
          </Button>
        </div>
      </form>
    </ModalCore>
  );
}

export const InitiativesHeader = observer(function InitiativesHeader() {
  const { workspaceSlug } = useParams();
  const [open, setOpen] = useState(false);
  const slug = workspaceSlug ?? "";
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink label="Initiatives" href={`/${slug}/initiatives/`} icon={<Target className="size-4" />} />
            }
          />
        </Breadcrumbs>
      </Header.LeftItem>
      <Header.RightItem>
        {initiativesStore.enabled[slug] && (
          <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
            New initiative
          </Button>
        )}
      </Header.RightItem>
      <NewInitiativeModal slug={slug} isOpen={open} onClose={() => setOpen(false)} />
    </Header>
  );
});

export const InitiativesList = observer(function InitiativesList({ workspaceSlug }: { workspaceSlug: string }) {
  const { allowPermissions } = useUserPermissions();
  const { getUserDetails } = useMember();
  const [busy, setBusy] = useState(false);
  const enabled = initiativesStore.enabled[workspaceSlug];
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);

  useEffect(() => {
    void initiativesStore.fetchEnabled(workspaceSlug).catch(() => undefined);
  }, [workspaceSlug]);
  useEffect(() => {
    if (enabled) void initiativesStore.fetchAll(workspaceSlug).catch(() => undefined);
  }, [workspaceSlug, enabled]);

  if (enabled === undefined) return null;
  if (!enabled)
    return (
      <div className="mx-auto mt-16 max-w-md space-y-3 text-center">
        <Target className="mx-auto size-8 text-tertiary" />
        <h3 className="text-16 font-medium text-primary">Initiatives are off</h3>
        <p className="text-13 text-tertiary">
          Group projects and epics under a goal and follow their progress in one place.
        </p>
        {isAdmin ? (
          <Button
            variant="primary"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              await initiativesStore
                .setEnabled(workspaceSlug, true)
                .catch(() => setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not turn them on." }));
              setBusy(false);
            }}
          >
            Turn on initiatives
          </Button>
        ) : (
          <p className="text-13 text-tertiary">Ask a workspace admin to turn them on.</p>
        )}
      </div>
    );

  const list = initiativesStore.bySlug[workspaceSlug] ?? [];
  if (!list.length)
    return (
      <p className="mt-16 text-center text-13 text-tertiary">No initiatives yet. Use “New initiative” to add one.</p>
    );

  return (
    <ul className="divide-y divide-subtle">
      {list.map((i) => (
        <li key={i.id}>
          <Link
            href={`/${workspaceSlug}/initiatives/${i.id}/`}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 hover:bg-layer-transparent-hover"
          >
            <span className="min-w-0 flex-1 truncate text-13 font-medium text-primary">{i.name}</span>
            <StateBadge state={i.state} />
            <span className="w-40 truncate text-12 text-tertiary">{dateRange(i.start_date, i.end_date)}</span>
            <span className="w-28 truncate text-12 text-tertiary">
              {i.lead ? (getUserDetails(i.lead)?.display_name ?? "") : ""}
            </span>
            <span className="text-12 text-tertiary">
              {i.project_ids.length} project{i.project_ids.length === 1 ? "" : "s"}
            </span>
            <EpicProgressBar progress={i.progress} />
          </Link>
        </li>
      ))}
    </ul>
  );
});
