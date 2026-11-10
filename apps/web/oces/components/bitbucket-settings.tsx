/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Copy, Eye, EyeOff } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AlertModalCore } from "@plane/ui";
import { copyTextToClipboard } from "@plane/utils";
import { BitbucketService } from "../services/bitbucket.service";
import type { TBitbucketSettings } from "../types";

const service = new BitbucketService();

function CopyField({ label, value, secret = false }: { label: string; value: string; secret?: boolean }) {
  const [shown, setShown] = useState(!secret);
  const copy = () =>
    void copyTextToClipboard(value).then(() =>
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Copied", message: `${label} copied.` })
    );
  return (
    <div className="flex flex-col gap-1">
      <span className="text-caption-sm-medium text-tertiary">{label}</span>
      <div className="flex items-center gap-2 rounded-md border border-subtle bg-layer-1 px-3 py-2">
        <code className="flex-1 truncate text-body-xs-regular text-primary">
          {shown ? value : "•".repeat(Math.min(value.length, 32))}
        </code>
        {secret && (
          <button
            type="button"
            aria-label={shown ? "Hide secret" : "Show secret"}
            onClick={() => setShown(!shown)}
            className="text-tertiary hover:text-primary"
          >
            {shown ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </button>
        )}
        <button type="button" aria-label={`Copy ${label}`} onClick={copy} className="text-tertiary hover:text-primary">
          <Copy className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

const fail = (error: any) =>
  setToast({
    type: TOAST_TYPE.ERROR,
    title: "Bitbucket",
    message: String(error?.error ?? error?.detail ?? "Something went wrong."),
  });

/** Workspace settings → Bitbucket: webhook URL + secret to paste into Bitbucket Cloud. */
export function BitbucketSettings({ workspaceSlug }: { workspaceSlug: string }) {
  const [data, setData] = useState<TBitbucketSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<"regenerate" | "disable" | null>(null);

  useEffect(() => {
    service.settings(workspaceSlug).then(setData).catch(fail);
  }, [workspaceSlug]);

  const run = async (action: () => Promise<TBitbucketSettings | void>) => {
    setBusy(true);
    try {
      const next = await action();
      setData(next ?? { enabled: false });
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  if (!data) return null;

  if (!data.enabled)
    return (
      <div className="flex flex-col items-start gap-3 rounded-md border border-subtle p-4">
        <p className="text-body-sm-regular text-secondary">
          Show Bitbucket Cloud pull requests on the work items they mention. Turning this on gives you a webhook URL and
          a secret to add in Bitbucket.
        </p>
        <Button
          variant="primary"
          size="sm"
          loading={busy}
          onClick={() => void run(() => service.newSecret(workspaceSlug))}
        >
          Turn on
        </Button>
      </div>
    );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <CopyField label="Webhook URL" value={data.webhook_url} />
        <CopyField label="Secret" value={data.secret} secret />
        <p className="text-caption-sm-regular text-tertiary">
          {data.last_event_at
            ? `Last delivery ${new Date(data.last_event_at).toLocaleString()} · ${data.pull_requests} pull request${data.pull_requests === 1 ? "" : "s"} seen`
            : "No deliveries yet."}
        </p>
      </div>

      <div className="flex flex-col gap-2 rounded-md border border-subtle p-4 text-body-xs-regular text-secondary">
        <span className="text-body-sm-medium text-primary">Set up in Bitbucket</span>
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            In Bitbucket, open the workspace (or one repository) → Settings → Webhooks → Add webhook. A workspace
            webhook covers every repository in it.
          </li>
          <li>Title: Plane. URL: the webhook URL above. Secret: the secret above.</li>
          <li>Triggers: choose from the full list and tick every Pull Request event. Save.</li>
          <li>
            Put the work item id in the pull request title, branch or description, e.g. <code>DEMO-7</code> or a branch
            like <code>feature/demo-7-login</code>. The pull request shows on that work item from its next event on.
          </li>
        </ol>
      </div>

      <div className="flex gap-2">
        <Button variant="secondary" size="sm" onClick={() => setConfirm("regenerate")}>
          New secret
        </Button>
        <Button variant="error-outline" size="sm" onClick={() => setConfirm("disable")}>
          Turn off
        </Button>
      </div>

      <AlertModalCore
        isOpen={confirm !== null}
        handleClose={() => setConfirm(null)}
        handleSubmit={() =>
          void run(() => (confirm === "disable" ? service.disable(workspaceSlug) : service.newSecret(workspaceSlug)))
        }
        isSubmitting={busy}
        title={confirm === "disable" ? "Turn off Bitbucket?" : "Make a new secret?"}
        content={
          confirm === "disable"
            ? "Plane will reject deliveries from Bitbucket. Pull requests already shown stay on their work items. Remove the webhook in Bitbucket too."
            : "The current secret stops working right away. Paste the new one into the Bitbucket webhook."
        }
        primaryButtonText={{
          default: confirm === "disable" ? "Turn off" : "Make new secret",
          loading: confirm === "disable" ? "Turning off" : "Saving",
        }}
      />
    </div>
  );
}
