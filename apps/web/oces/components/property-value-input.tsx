/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { AlignLeft, Link, Mail, Type } from "lucide-react";
import {
  BooleanPropertyIcon,
  DropdownPropertyIcon,
  DueDatePropertyIcon,
  HashPropertyIcon,
  RelationPropertyIcon,
  UserPropertyIcon,
} from "@plane/propel/icons";
import { CustomSearchSelect, ToggleSwitch } from "@plane/ui";
import { cn, renderFormattedPayloadDate } from "@plane/utils";
import { DateDropdown } from "@/components/dropdowns/date";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
import { isEmptyValue, isRichText } from "../store/properties.store";
import type { TProperty, TPropertyValue } from "../types";

type Props = {
  property: TProperty;
  projectId: string;
  value: TPropertyValue | undefined;
  onChange: (value: TPropertyValue) => void;
  disabled?: boolean;
  /** compact controls for the sidebar; the create form uses bordered ones */
  variant?: "sidebar" | "form";
  error?: string;
};

export const propertyIcon = (p: TProperty) => {
  if (p.property_type === "BOOLEAN") return BooleanPropertyIcon;
  if (p.property_type === "OPTION") return DropdownPropertyIcon;
  if (p.property_type === "DATETIME") return DueDatePropertyIcon;
  if (p.property_type === "DECIMAL") return HashPropertyIcon;
  if (p.property_type === "RELATION" && p.relation_type === "USER") return UserPropertyIcon;
  if (p.property_type === "RELATION" && p.relation_type === "ISSUE") return RelationPropertyIcon;
  if (p.property_type === "URL") return Link;
  if (p.property_type === "EMAIL") return Mail;
  if (isRichText(p) || p.settings?.display_format === "multi-line") return AlignLeft;
  return Type;
};

const dot = (color?: string) => (
  <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: color || "var(--text-color-tertiary)" }} />
);

export const htmlToText = (html: string) => new DOMParser().parseFromString(html, "text/html").body.textContent ?? "";
const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const textToHtml = (text: string) =>
  text
    .split(/\n{2,}/)
    .map((p) => `<p>${escape(p).replace(/\n/g, "<br />")}</p>`)
    .join("");

/** A text-like field that saves when it loses focus (or on Enter for single-line). */
function TextField(props: {
  value: string;
  onCommit: (v: string) => void;
  multiline: boolean;
  type?: string;
  placeholder: string;
  disabled: boolean;
  className: string;
}) {
  const { value, onCommit, multiline, type = "text", placeholder, disabled, className } = props;
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const commit = () => draft !== value && onCommit(draft);
  if (multiline)
    return (
      <textarea
        value={draft}
        disabled={disabled}
        placeholder={placeholder}
        rows={2}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        className={cn(className, "resize-y")}
      />
    );
  return (
    <input
      type={type}
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      step={type === "number" ? "any" : undefined}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          (e.target as HTMLInputElement).blur();
        }
      }}
      className={className}
    />
  );
}

export const PropertyValueInput = observer(function PropertyValueInput(props: Props) {
  const { property: p, projectId, value, onChange, disabled = false, variant = "sidebar", error } = props;
  const form = variant === "form";
  const box = cn(
    "w-full rounded-sm bg-transparent px-2 py-1 text-body-xs-medium text-primary outline-none placeholder:text-placeholder",
    form ? "border-[0.5px] border-subtle" : "hover:bg-layer-transparent-hover focus:bg-layer-transparent-hover",
    error && "border-danger-strong"
  );
  const placeholder = form ? p.display_name + (p.is_required ? " *" : "") : "Empty";

  if (p.property_type === "BOOLEAN")
    return (
      <div className="flex h-7.5 items-center px-2">
        <ToggleSwitch value={value === true} onChange={(v) => onChange(v)} disabled={disabled} size="sm" />
      </div>
    );

  if (p.property_type === "DATETIME")
    return (
      <DateDropdown
        value={typeof value === "string" ? value : null}
        onChange={(d) => onChange((d && renderFormattedPayloadDate(d)) || null)}
        placeholder={placeholder}
        buttonVariant={form ? "border-with-text" : "transparent-with-text"}
        disabled={disabled}
        className="group w-full grow"
        buttonContainerClassName="w-full text-left h-7.5"
        buttonClassName={cn("text-body-xs-medium", !value && "text-placeholder")}
        hideIcon={!form}
        clearIconClassName="h-3 w-3 hidden group-hover:inline"
      />
    );

  if (p.property_type === "OPTION") {
    const options = p.options.filter(
      (o) => o.is_active || (Array.isArray(value) ? value.includes(o.id) : value === o.id)
    );
    const selected = Array.isArray(value) ? value : value ? [String(value)] : [];
    const label = selected.length
      ? options
          .filter((o) => selected.includes(o.id))
          .map((o) => o.name)
          .join(", ")
      : placeholder;
    const common = {
      disabled,
      maxHeight: "lg" as const,
      className: "w-full",
      buttonClassName: cn(box, "h-7.5 text-left", !selected.length && "text-placeholder"),
      label: <span className="truncate">{label}</span>,
      options: options.map((o) => ({
        value: o.id,
        query: o.name,
        content: (
          <span className="flex items-center gap-1.5">
            {dot(o.logo_props?.color)}
            <span>{o.name}</span>
          </span>
        ),
      })),
    };
    return p.is_multi ? (
      <CustomSearchSelect {...common} multiple value={selected} onChange={(v: string[]) => onChange(v)} />
    ) : (
      <CustomSearchSelect
        {...common}
        value={selected[0] ?? null}
        onChange={(v: string) => onChange(v === selected[0] ? null : v)}
      />
    );
  }

  if (p.property_type === "RELATION" && p.relation_type === "USER") {
    const common = {
      projectId,
      disabled,
      placeholder,
      buttonVariant: (form ? "border-with-text" : "transparent-with-text") as "border-with-text",
      className: "group w-full grow",
      buttonContainerClassName: "w-full text-left h-7.5",
      buttonClassName: cn("justify-between text-body-xs-medium", isEmptyValue(value) && "text-placeholder"),
      hideIcon: isEmptyValue(value) && !form,
    };
    return p.is_multi ? (
      <MemberDropdown
        {...common}
        multiple
        value={Array.isArray(value) ? value : []}
        onChange={(v: string[]) => onChange(v)}
      />
    ) : (
      <MemberDropdown
        {...common}
        multiple={false}
        value={typeof value === "string" ? value : null}
        onChange={(v: string | null) => onChange(v === value ? null : v)}
      />
    );
  }

  if (p.property_type === "RELATION" && p.relation_type === "ISSUE") {
    // shortcut: no work item picker yet; set these through the API or MCP until one exists
    const count = Array.isArray(value) ? value.length : value ? 1 : 0;
    return (
      <span className="px-2 text-body-xs-medium text-tertiary">
        {count ? `${count} work item${count > 1 ? "s" : ""}` : "Set through the API"}
      </span>
    );
  }

  if (isRichText(p)) {
    return (
      <TextField
        value={typeof value === "string" ? htmlToText(value) : ""}
        onCommit={(t) => onChange(t.trim() ? textToHtml(t) : null)}
        multiline
        placeholder={placeholder}
        disabled={disabled}
        className={box}
      />
    );
  }

  const text = value === null || value === undefined ? "" : String(value);
  return (
    <TextField
      value={text}
      onCommit={(t) => {
        if (p.property_type === "DECIMAL") onChange(t.trim() === "" ? null : Number(t));
        else onChange(t.trim() === "" ? null : t);
      }}
      multiline={p.property_type === "TEXT" && p.settings?.display_format === "multi-line"}
      type={
        p.property_type === "DECIMAL"
          ? "number"
          : p.property_type === "EMAIL"
            ? "email"
            : p.property_type === "URL"
              ? "url"
              : "text"
      }
      placeholder={placeholder}
      disabled={disabled || (p.property_type === "TEXT" && p.settings?.display_format === "readonly")}
      className={box}
    />
  );
});
