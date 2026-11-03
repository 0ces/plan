/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";
import * as Y from "yjs";
import { getAllDocumentFormatsFromDocumentEditorBinaryData } from "@plane/editor";
import { pageContent, replaceDocument } from "@/oces/page-content";

vi.mock("@/env", () => ({ env: { LIVE_SERVER_SECRET_KEY: "k" } }));

const REPORT = `
<h1>Incident 42</h1>
<h2>Summary</h2>
<p>We <strong>lost</strong> writes; see <a href="https://example.com/runbook">the runbook</a> and <code>pg_dump</code>.</p>
<ul><li><p>one</p><ul><li><p>nested</p></li></ul></li><li><p>two</p></li></ul>
<ol><li><p>first</p></li></ol>
<table><tbody><tr><th><p>Host</p></th><th><p>State</p></th></tr><tr><td><p>svr3</p></td><td><p>ok</p></td></tr></tbody></table>
`;

const decode = (b64: string) => new Uint8Array(Buffer.from(b64, "base64"));

describe("page content from HTML", () => {
  it("keeps headings, lists, marks, links and tables through HTML -> Yjs -> HTML", () => {
    const { formats } = pageContent(REPORT, "Incident 42");
    const html = formats.contentHTML;
    for (const part of [
      "<h1",
      "<h2",
      "<strong>lost</strong>",
      'href="https://example.com/runbook"',
      "<code",
      "pg_dump",
      "<ul",
      "nested",
      "<ol",
      "<table",
      "svr3",
    ])
      expect(html).toContain(part);
    // nested list survives as a list inside a list item
    expect(html).toMatch(/<li[^>]*>.*<ul[^>]*>.*nested/s);
    expect(formats.titleHTML).toBe("Incident 42");
  });

  it("produces a binary the editor loads back to the same HTML", () => {
    const { formats } = pageContent(REPORT, "Incident 42");
    const again = getAllDocumentFormatsFromDocumentEditorBinaryData(decode(formats.contentBinaryEncoded), true);
    expect(again.contentHTML).toBe(formats.contentHTML);
  });

  it("treats empty HTML as an empty paragraph", () => {
    expect(pageContent("  ").formats.contentHTML).toContain("<p");
  });

  it("replaces an open document in place", () => {
    const open = new Y.Doc();
    Y.applyUpdate(open, pageContent("<p>old text</p>", "Old").binary);
    const updates: Uint8Array[] = [];
    open.on("update", (u: Uint8Array) => updates.push(u));

    replaceDocument(open, pageContent("<h2>new</h2><p>body</p>", "New").binary);

    const after = getAllDocumentFormatsFromDocumentEditorBinaryData(Y.encodeStateAsUpdate(open), true);
    expect(after.contentHTML).toContain("new");
    expect(after.contentHTML).not.toContain("old text");
    expect(after.titleHTML).toBe("New");
    // one transaction, so connected editors get a single update
    expect(updates).toHaveLength(1);
  });
});
