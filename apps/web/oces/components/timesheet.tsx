/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { ChevronDown, ChevronLeft, ChevronRight, Timer } from "lucide-react";
import { Link } from "react-router";
import { Button } from "@plane/propel/button";
import { Breadcrumbs, Header } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { ButtonAvatars } from "@/components/dropdowns/member/avatar";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { WorkLogsService } from "../services/worklogs.service";
import { formatDuration } from "../store/worklogs.store";
import type { TWorkLog } from "../types";

const service = new WorkLogsService();

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Monday of the week that contains `d`, at local midnight. */
function mondayOf(d: Date) {
  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7));
  return day;
}

const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

const fmt = (d: Date, opts: Intl.DateTimeFormatOptions) => d.toLocaleDateString(undefined, opts);

const cell = (minutes: number | undefined) => (minutes ? formatDuration(minutes) : "");

type Row = { id: string; label: React.ReactNode; days: Record<string, number>; total: number };

function rowsBy(logs: TWorkLog[], key: (l: TWorkLog) => string, label: (l: TWorkLog) => React.ReactNode): Row[] {
  const rows = new Map<string, Row>();
  for (const log of logs) {
    const id = key(log);
    const row = rows.get(id) ?? { id, label: label(log), days: {}, total: 0 };
    row.days[log.logged_at] = (row.days[log.logged_at] ?? 0) + log.duration;
    row.total += log.duration;
    rows.set(id, row);
  }
  // oxlint-disable-next-line unicorn/no-array-sort -- sorts a fresh copy (lib has no toSorted)
  return [...rows.values()].sort((a, b) => b.total - a.total);
}

export function TimesheetHeader() {
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label="Timesheet" icon={<Timer className="size-4" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}

type Props = { workspaceSlug: string; projectId: string };

/** Hours per person per day for one week, each person expandable into the work items they logged on. */
export const Timesheet = observer(function Timesheet({ workspaceSlug, projectId }: Props) {
  const { getProjectById } = useProject();
  const { getUserDetails } = useMember();
  const project = getProjectById(projectId);
  const enabled = !!project?.is_time_tracking_enabled;
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [logs, setLogs] = useState<TWorkLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const from = iso(days[0]);
  const to = iso(days[6]);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    setLogs(null);
    setError(null);
    service
      .range(workspaceSlug, projectId, from, to)
      .then((res) => alive && setLogs(res.results))
      .catch((e: any) => alive && setError(String(e?.error ?? e?.detail ?? "Could not load the timesheet.")));
    return () => {
      alive = false;
    };
  }, [enabled, workspaceSlug, projectId, from, to]);

  if (project && !enabled)
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <Timer className="size-8 text-tertiary" />
        <p className="text-body-sm-medium text-primary">Time tracking is off for this project.</p>
        <p className="text-body-xs-regular text-tertiary">An admin can turn it on in Project settings → Features.</p>
      </div>
    );

  const people = rowsBy(
    logs ?? [],
    (l) => l.logged_by,
    (l) => (
      <span className="flex items-center gap-2">
        <ButtonAvatars showTooltip={false} userIds={l.logged_by} />
        {getUserDetails(l.logged_by)?.display_name ?? "Unknown"}
      </span>
    )
  );
  const itemsOf = (userId: string) =>
    rowsBy(
      (logs ?? []).filter((l) => l.logged_by === userId),
      (l) => l.work_item_id,
      (l) => (
        <Link
          to={`/${workspaceSlug}/browse/${project?.identifier}-${l.work_item?.sequence_id}/`}
          className="truncate text-secondary hover:text-primary hover:underline"
        >
          <span className="mr-1.5 text-tertiary">
            {project?.identifier}-{l.work_item?.sequence_id}
          </span>
          {l.work_item?.name}
        </Link>
      )
    );
  const dayTotal = (d: string) => (logs ?? []).filter((l) => l.logged_at === d).reduce((s, l) => s + l.duration, 0);
  const weekTotal = (logs ?? []).reduce((s, l) => s + l.duration, 0);
  const today = iso(new Date());

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          aria-label="Previous week"
          onClick={() => setWeekStart(addDays(weekStart, -7))}
        >
          <ChevronLeft className="size-4" />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          aria-label="Next week"
          onClick={() => setWeekStart(addDays(weekStart, 7))}
        >
          <ChevronRight className="size-4" />
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setWeekStart(mondayOf(new Date()))}>
          This week
        </Button>
        <span className="ml-2 text-body-sm-medium text-primary">
          {fmt(days[0], { day: "numeric", month: "short" })} –{" "}
          {fmt(days[6], { day: "numeric", month: "short", year: "numeric" })}
        </span>
        <span className="ml-auto text-body-sm-medium text-secondary">Total {formatDuration(weekTotal)}</span>
      </div>

      {error && <p className="text-body-sm-regular text-danger-primary">{error}</p>}

      <div className="overflow-x-auto rounded-md border border-subtle">
        <table className="w-full min-w-[720px] border-collapse whitespace-nowrap text-body-xs-regular">
          <thead>
            <tr className="border-b border-subtle bg-layer-1 text-tertiary">
              <th className="px-3 py-2 text-left font-medium">Person</th>
              {days.map((d) => (
                <th
                  key={iso(d)}
                  className={`w-20 px-2 py-2 text-right font-medium ${iso(d) === today ? "text-accent-primary" : ""}`}
                >
                  {fmt(d, { weekday: "short" })} {d.getDate()}
                </th>
              ))}
              <th className="w-20 px-3 py-2 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {logs === null && !error && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-tertiary">
                  Loading…
                </td>
              </tr>
            )}
            {logs !== null && people.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-tertiary">
                  No time logged this week.
                </td>
              </tr>
            )}
            {people.map((person) => (
              <Fragment key={person.id}>
                <tr className="border-b border-subtle text-primary">
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="flex items-center gap-1"
                      aria-expanded={!!open[person.id]}
                      onClick={() => setOpen({ ...open, [person.id]: !open[person.id] })}
                    >
                      <ChevronDown className={`size-3.5 text-tertiary ${open[person.id] ? "" : "-rotate-90"}`} />
                      {person.label}
                    </button>
                  </td>
                  {days.map((d) => (
                    <td key={iso(d)} className="px-2 py-2 text-right tabular-nums">
                      {cell(person.days[iso(d)])}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right font-medium tabular-nums">{formatDuration(person.total)}</td>
                </tr>
                {open[person.id] &&
                  itemsOf(person.id).map((item) => (
                    <tr key={item.id} className="border-b border-subtle bg-layer-1/40 text-secondary">
                      <td className="max-w-72 py-1.5 pr-3 pl-10">{item.label}</td>
                      {days.map((d) => (
                        <td key={iso(d)} className="px-2 py-1.5 text-right tabular-nums">
                          {cell(item.days[iso(d)])}
                        </td>
                      ))}
                      <td className="px-3 py-1.5 text-right tabular-nums">{formatDuration(item.total)}</td>
                    </tr>
                  ))}
              </Fragment>
            ))}
          </tbody>
          {people.length > 0 && (
            <tfoot>
              <tr className="bg-layer-1 font-medium text-primary">
                <td className="px-3 py-2">Total</td>
                {days.map((d) => (
                  <td key={iso(d)} className="px-2 py-2 text-right tabular-nums">
                    {cell(dayTotal(iso(d)))}
                  </td>
                ))}
                <td className="px-3 py-2 text-right tabular-nums">{formatDuration(weekTotal)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
});
