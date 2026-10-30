/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useNavigate } from "react-router";
import { X } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { ISearchIssueResponse, TProjectIssuesSearchParams } from "@plane/types";
import { AlertModalCore, CustomSearchSelect, CustomSelect } from "@plane/ui";
import { renderFormattedPayloadDate } from "@plane/utils";
import { ExistingIssuesListModal } from "@/components/core/modals/existing-issues-list-modal";
import { DateDropdown } from "@/components/dropdowns/date";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
import { useProject } from "@/hooks/store/use-project";
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { ProjectService } from "@/services/project";
import { initiativesService, initiativesStore } from "../store/initiatives.store";
import type { TInitiativeInput, TInitiativeState, TLinkedWorkItem } from "../types";
import { EpicProgressBar } from "./epic-progress-bar";
import { STATE_STYLE, StateBadge } from "./initiatives-list";
import { htmlToText, textToHtml } from "./property-value-input";

const projectService = new ProjectService();

type Props = { workspaceSlug: string; initiativeId: string };

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-13 font-medium text-secondary">{title}</h4>
        {action}
      </div>
      {children}
    </section>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="rounded-sm p-0.5 text-tertiary hover:text-danger-primary"
    >
      <X className="size-3.5" />
    </button>
  );
}

export const InitiativeDetail = observer(function InitiativeDetail({ workspaceSlug, initiativeId }: Props) {
  const navigate = useNavigate();
  const { joinedProjectIds, getProjectById } = useProject();
  const { data: me } = useUser();
  const { allowPermissions } = useUserPermissions();
  const [items, setItems] = useState<{ epics: TLinkedWorkItem[]; "work-items": TLinkedWorkItem[] }>({
    epics: [],
    "work-items": [],
  });
  const [picker, setPicker] = useState<"epics" | "work-items" | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const initiative = initiativesStore.byId[initiativeId];

  const loadItems = useCallback(async () => {
    const [epics, workItems] = await Promise.all([
      initiativesService.linked(workspaceSlug, initiativeId, "epics"),
      initiativesService.linked(workspaceSlug, initiativeId, "work-items"),
    ]);
    setItems({ epics, "work-items": workItems });
  }, [workspaceSlug, initiativeId]);

  useEffect(() => {
    void initiativesStore.fetchOne(workspaceSlug, initiativeId).catch(() => undefined);
    void loadItems().catch(() => undefined);
  }, [workspaceSlug, initiativeId, loadItems]);

  useEffect(() => {
    setName(initiative?.name ?? "");
    setDescription(htmlToText(initiative?.description_html ?? ""));
  }, [initiative?.name, initiative?.description_html]);

  if (!initiative) return null;

  const fail = (message: string) => (error: any) =>
    setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: String(Object.values(error ?? {})[0] ?? message) });
  const save = (data: TInitiativeInput) =>
    initiativesStore.update(workspaceSlug, initiativeId, data).catch(fail("Could not save."));
  const link = async (kind: "projects" | "epics" | "work-items", ids: string[], add: boolean) => {
    await initiativesStore.link(workspaceSlug, initiativeId, kind, ids, add).catch(fail("Could not update links."));
    if (kind !== "projects") await loadItems().catch(() => undefined);
  };

  const canDelete =
    initiative.created_by === me?.id ||
    allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);
  const linkedProjects = initiative.project_ids.map((id) => getProjectById(id)).filter((p) => !!p);
  const otherProjects = joinedProjectIds.filter((id) => !initiative.project_ids.includes(id));
  const searchProject = joinedProjectIds[0];

  const itemRow = (kind: "epics" | "work-items", item: TLinkedWorkItem) => {
    const ident = `${getProjectById(item.project)?.identifier ?? "?"}-${item.sequence_id}`;
    return (
      <li key={item.id} className="flex items-center gap-3 px-3 py-2">
        <Link
          href={`/${workspaceSlug}/browse/${ident}/`}
          className="flex min-w-0 flex-1 items-center gap-3 hover:underline"
        >
          <span className="shrink-0 text-12 text-tertiary">{ident}</span>
          <span className="truncate text-13 text-primary">{item.name}</span>
        </Link>
        <RemoveButton label={`Unlink ${ident}`} onClick={() => void link(kind, [item.id], false)} />
      </li>
    );
  };

  const itemSection = (kind: "epics" | "work-items", title: string, hint: string) => (
    <Section
      title={title}
      action={
        searchProject && (
          <Button variant="secondary" size="sm" onClick={() => setPicker(kind)}>
            Add
          </Button>
        )
      }
    >
      {items[kind].length ? (
        <ul className="divide-y divide-subtle rounded-md border-[0.5px] border-subtle">
          {items[kind].map((item) => itemRow(kind, item))}
        </ul>
      ) : (
        <p className="text-12 text-tertiary">{hint}</p>
      )}
    </Section>
  );

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-5 py-6">
      <div className="space-y-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => name.trim() && name.trim() !== initiative.name && void save({ name: name.trim() })}
          aria-label="Initiative name"
          className="w-full bg-transparent text-h4-medium text-primary outline-none"
          maxLength={255}
        />
        <div className="flex flex-wrap items-center gap-2">
          <CustomSelect
            value={initiative.state}
            onChange={(state: TInitiativeState) => void save({ state })}
            label={<StateBadge state={initiative.state} />}
            buttonClassName="rounded-md px-1 py-1"
          >
            {(Object.keys(STATE_STYLE) as TInitiativeState[]).map((s) => (
              <CustomSelect.Option key={s} value={s}>
                {STATE_STYLE[s].label}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
          <MemberDropdown
            value={initiative.lead}
            multiple={false}
            onChange={(lead: string | null) => void save({ lead: lead === initiative.lead ? null : lead })}
            placeholder="Lead"
            buttonVariant="border-with-text"
          />
          <DateDropdown
            value={initiative.start_date}
            onChange={(d) => void save({ start_date: (d && renderFormattedPayloadDate(d)) || null })}
            placeholder="Start date"
            buttonVariant="border-with-text"
            maxDate={initiative.end_date ? new Date(initiative.end_date) : undefined}
          />
          <DateDropdown
            value={initiative.end_date}
            onChange={(d) => void save({ end_date: (d && renderFormattedPayloadDate(d)) || null })}
            placeholder="End date"
            buttonVariant="border-with-text"
            minDate={initiative.start_date ? new Date(initiative.start_date) : undefined}
          />
          <div className="ml-auto">
            <EpicProgressBar progress={initiative.progress} />
          </div>
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() =>
            description !== htmlToText(initiative.description_html) &&
            void save({ description_html: description.trim() ? textToHtml(description) : "<p></p>" })
          }
          placeholder="What is this initiative for?"
          rows={3}
          className="w-full resize-y rounded-md border-[0.5px] border-subtle bg-transparent px-3 py-2 text-13 text-primary outline-none placeholder:text-placeholder"
        />
      </div>

      <Section
        title="Projects"
        action={
          otherProjects.length > 0 && (
            <CustomSearchSelect
              value={null}
              onChange={(id: string) => void link("projects", [id], true)}
              label={<span className="text-12">Add project</span>}
              buttonClassName="rounded-md border-[0.5px] border-subtle px-2 py-1"
              options={otherProjects.map((id) => {
                const p = getProjectById(id);
                return { value: id, query: `${p?.name} ${p?.identifier}`, content: <span>{p?.name}</span> };
              })}
            />
          )
        }
      >
        {linkedProjects.length ? (
          <ul className="flex flex-wrap gap-2">
            {linkedProjects.map((p) => (
              <li
                key={p.id}
                className="flex items-center gap-1.5 rounded-md border-[0.5px] border-subtle px-2 py-1 text-13"
              >
                <Link href={`/${workspaceSlug}/projects/${p.id}/issues/`} className="hover:underline">
                  {p.name}
                </Link>
                <RemoveButton label={`Remove ${p.name}`} onClick={() => void link("projects", [p.id], false)} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-12 text-tertiary">Every work item in a linked project counts toward progress.</p>
        )}
      </Section>

      {itemSection("epics", "Epics", "The children of linked epics count toward progress.")}
      {itemSection("work-items", "Work items", "Link single work items that sit outside the projects above.")}

      {canDelete && (
        <div className="border-t border-subtle pt-4">
          <Button variant="error-outline" size="sm" onClick={() => setDeleting(true)}>
            Delete initiative
          </Button>
        </div>
      )}

      {searchProject && (
        <ExistingIssuesListModal
          workspaceSlug={workspaceSlug}
          isOpen={picker !== null}
          handleClose={() => setPicker(null)}
          searchParams={{}}
          selectedWorkItemIds={picker ? items[picker].map((i) => i.id) : []}
          workItemSearchServiceCallback={(params: TProjectIssuesSearchParams) =>
            projectService.projectIssuesSearch(workspaceSlug, searchProject, { ...params, workspace_search: true })
          }
          handleOnSubmit={async (picked: ISearchIssueResponse[]) => {
            if (picker)
              await link(
                picker,
                picked.map((i) => i.id),
                true
              );
          }}
        />
      )}
      <AlertModalCore
        isOpen={deleting}
        handleClose={() => setDeleting(false)}
        isSubmitting={false}
        title={`Delete "${initiative.name}"?`}
        content="The initiative and its links are removed. Projects and work items stay as they are."
        primaryButtonText={{ loading: "Deleting", default: "Delete" }}
        handleSubmit={async () => {
          await initiativesStore
            .remove(workspaceSlug, initiativeId)
            .then(() => navigate(`/${workspaceSlug}/initiatives/`))
            .catch(fail("Could not delete."));
          setDeleting(false);
        }}
      />
    </div>
  );
});
