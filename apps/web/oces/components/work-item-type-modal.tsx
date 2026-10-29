/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Button } from "@plane/propel/button";
import { EmojiPicker, Logo } from "@plane/propel/emoji-icon-picker";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TLogoProps } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, TextArea } from "@plane/ui";
import { workItemTypesStore } from "../store/work-item-types.store";
import type { TWorkItemType } from "../types";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  type?: TWorkItemType; // edit when set, create otherwise
};

const DEFAULT_LOGO: TLogoProps = { in_use: "icon", icon: { name: "label", color: "#6e7b8b" } };

export function WorkItemTypeModal({ isOpen, onClose, workspaceSlug, projectId, type }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [logo, setLogo] = useState<TLogoProps>(DEFAULT_LOGO);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName(type?.name ?? "");
    setDescription(type?.description ?? "");
    setLogo((type?.logo_props as TLogoProps) ?? DEFAULT_LOGO);
  }, [isOpen, type]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    const data = { name: name.trim(), description, logo_props: logo };
    try {
      if (type) await workItemTypesStore.update(workspaceSlug, projectId, type.id, data);
      else await workItemTypesStore.create(workspaceSlug, projectId, data);
      onClose();
    } catch (error: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: error?.error ?? "Could not save the type." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <h3 className="text-h4-medium text-secondary">{type ? "Edit work item type" : "New work item type"}</h3>
        <div className="flex items-start gap-3">
          <EmojiPicker
            iconType="material"
            isOpen={isPickerOpen}
            handleToggle={setIsPickerOpen}
            buttonClassName="flex size-9 shrink-0 items-center justify-center rounded-md border-[0.5px] border-subtle"
            label={<Logo logo={logo} size={18} />}
            onChange={(val: any) => {
              const value = val?.type === "emoji" ? { value: val.value } : val?.value;
              setLogo({ in_use: val?.type, [val?.type]: value } as TLogoProps);
            }}
          />
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name, e.g. Story"
            className="w-full"
            maxLength={255}
          />
        </div>
        <TextArea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          className="min-h-20 w-full"
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={saving} disabled={!name.trim()}>
            {type ? "Save" : "Create"}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
}
