/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomSelect, EModalPosition, EModalWidth, Input, ModalCore, TextArea, ToggleSwitch } from "@plane/ui";
import { propertiesStore } from "../store/properties.store";
import type { TProperty, TPropertyInput } from "../types";

/** The kinds a user picks from; each maps to the API's property_type (+ relation_type / settings). */
export const KINDS = [
  { key: "text", label: "Text", input: { property_type: "TEXT", settings: { display_format: "single-line" } } },
  {
    key: "paragraph",
    label: "Paragraph",
    input: { property_type: "TEXT", settings: { display_format: "multi-line" } },
  },
  { key: "number", label: "Number", input: { property_type: "DECIMAL" } },
  { key: "checkbox", label: "Checkbox", input: { property_type: "BOOLEAN" } },
  { key: "date", label: "Date", input: { property_type: "DATETIME", settings: { display_format: "MMM dd, yyyy" } } },
  { key: "dropdown", label: "Dropdown", input: { property_type: "OPTION" }, multi: true },
  { key: "url", label: "URL", input: { property_type: "URL" } },
  { key: "email", label: "Email", input: { property_type: "EMAIL" } },
  { key: "member", label: "Member", input: { property_type: "RELATION", relation_type: "USER" }, multi: true },
  { key: "rich", label: "Rich text", input: { property_type: "RELATION", relation_type: "RICH_TEXT" } },
] as const satisfies readonly { key: string; label: string; input: TPropertyInput; multi?: boolean }[];

export const kindOf = (p: TProperty) =>
  KINDS.find(
    (k) =>
      k.input.property_type === p.property_type &&
      (!("relation_type" in k.input) || k.input.relation_type === p.relation_type) &&
      (k.input.property_type !== "TEXT" ||
        k.input.settings.display_format === (p.settings?.display_format ?? "single-line"))
  ) ?? (p.relation_type === "ISSUE" ? { key: "issue", label: "Work item", input: {}, multi: true } : KINDS[0]);

type Option = { id?: string; key: string; name: string; is_default: boolean };

let nextKey = 0;
const newOption = (): Option => ({ key: `new-${nextKey++}`, name: "", is_default: false });

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  typeId: string;
  property?: TProperty;
};

export function PropertyModal({ isOpen, onClose, workspaceSlug, projectId, typeId, property }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<string>("text");
  const [required, setRequired] = useState(false);
  const [multi, setMulti] = useState(false);
  const [options, setOptions] = useState<Option[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName(property?.display_name ?? "");
    setDescription(property?.description ?? "");
    setKind(property ? kindOf(property).key : "text");
    setRequired(property?.is_required ?? false);
    setMulti(property?.is_multi ?? false);
    setOptions(
      property?.options.map((o) => ({ id: o.id, key: o.id, name: o.name, is_default: o.is_default })) ?? [newOption()]
    );
  }, [isOpen, property]);

  const spec = KINDS.find((k) => k.key === kind);
  const isDropdown = kind === "dropdown";
  const canMulti = !!spec && "multi" in spec && spec.multi;
  const cleanOptions = options.map((o) => ({ ...o, name: o.name.trim() })).filter((o) => o.name);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !spec) return;
    if (isDropdown && !cleanOptions.length) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Add at least one option." });
      return;
    }
    setSaving(true);
    const base: TPropertyInput = {
      display_name: name.trim(),
      description,
      is_required: required,
      is_multi: canMulti ? multi : false,
    };
    try {
      if (property) {
        await propertiesStore.update(workspaceSlug, projectId, typeId, property.id, base);
        if (isDropdown) {
          await propertiesStore.syncOptions(workspaceSlug, projectId, property, cleanOptions);
          await propertiesStore.fetchForType(workspaceSlug, projectId, typeId, true);
        }
      } else {
        await propertiesStore.create(workspaceSlug, projectId, typeId, {
          ...spec.input,
          ...base,
          options: isDropdown ? cleanOptions.map((o) => ({ name: o.name, is_default: o.is_default })) : undefined,
        });
      }
      onClose();
    } catch (error: any) {
      const message = Object.values(error ?? {})[0] ?? "Could not save the property.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: String(message) });
    } finally {
      setSaving(false);
    }
  };

  const setOption = (i: number, patch: Partial<Option>) =>
    setOptions((prev) =>
      prev.map((o, j) => {
        if (j === i) return { ...o, ...patch };
        // one default unless the property is multi-value
        return patch.is_default && !multi ? { ...o, is_default: false } : o;
      })
    );

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <h3 className="text-h4-medium text-secondary">{property ? "Edit property" : "New property"}</h3>
        <div className="flex gap-3">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name, e.g. Client"
            className="w-full"
            maxLength={255}
          />
          <CustomSelect
            value={kind}
            onChange={(k: string) => setKind(k)}
            disabled={!!property}
            buttonClassName="border-[0.5px] border-subtle rounded-md px-3 py-2 text-13 w-36"
            label={<span>{property ? kindOf(property).label : (spec?.label ?? "Kind")}</span>}
          >
            {KINDS.map((k) => (
              <CustomSelect.Option key={k.key} value={k.key}>
                {k.label}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>
        <TextArea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          className="min-h-16 w-full"
        />

        {isDropdown && (
          <div className="space-y-2">
            <p className="text-13 font-medium text-secondary">Options</p>
            {options.map((o, i) => (
              <div key={o.key} className="flex items-center gap-2">
                <Input
                  value={o.name}
                  onChange={(e) => setOption(i, { name: e.target.value })}
                  placeholder={`Option ${i + 1}`}
                  className="w-full"
                  maxLength={255}
                />
                <label className="flex shrink-0 items-center gap-1 text-12 text-tertiary">
                  <input
                    type="checkbox"
                    checked={o.is_default}
                    onChange={(e) => setOption(i, { is_default: e.target.checked })}
                  />
                  Default
                </label>
                <button
                  type="button"
                  aria-label="Remove option"
                  className="shrink-0 rounded-sm p-1 text-tertiary hover:text-danger-primary"
                  onClick={() => setOptions((prev) => prev.filter((_, j) => j !== i))}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              type="button"
              prependIcon={<Plus className="size-3.5" />}
              onClick={() => setOptions((prev) => [...prev, newOption()])}
            >
              Add option
            </Button>
            {property && <p className="text-12 text-tertiary">Removing an option clears it from every work item.</p>}
          </div>
        )}

        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2 text-13 text-secondary">
            <ToggleSwitch value={required} onChange={setRequired} size="sm" label="Required when creating" />
            Required when creating
          </div>
          {canMulti && (
            <div className="flex items-center gap-2 text-13 text-secondary">
              <ToggleSwitch value={multi} onChange={setMulti} size="sm" label="Allow several values" />
              Allow several values
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={saving} disabled={!name.trim()}>
            {property ? "Save" : "Create"}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
}
