/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Page content written through the public API (apps/api/plane/oces/page_views.py).
// The editor loads pages from description_binary (a Yjs document), so HTML sent to
// the API is converted here with the same helpers the editor uses when it opens a
// page for the first time. If the page is open right now, its in-memory document is
// replaced in one transaction, so open editors see the new content instead of
// later saving the old one over it.

import type { Hocuspocus } from "@hocuspocus/server";
import type { Request, Response } from "express";
import * as Y from "yjs";
import { Controller, Middleware, Post } from "@plane/decorators";
import {
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
} from "@plane/editor";
import { logger } from "@plane/logger";
import { requireSecretKey } from "@/lib/auth-middleware";

const FRAGMENTS = ["default", "title"] as const;

export function pageContent(html: string, name?: string) {
  const binary = getBinaryDataFromDocumentEditorHTMLString(html.trim() ? html : "<p></p>", name);
  const formats = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, true);
  return { binary, formats };
}

/** Replace the body and title of a loaded document with the ones in `binary`. */
export function replaceDocument(doc: Y.Doc, binary: Uint8Array) {
  const fresh = new Y.Doc();
  Y.applyUpdate(fresh, binary);
  doc.transact(() => {
    for (const key of FRAGMENTS) {
      const target = doc.getXmlFragment(key);
      const nodes = fresh
        .getXmlFragment(key)
        .toArray()
        .map((n) => (n as Y.XmlElement | Y.XmlText).clone());
      target.delete(0, target.length);
      target.insert(0, nodes);
    }
  });
}

@Controller("/oces/page-content")
export class OcesPageContentController {
  [key: string]: unknown;
  private readonly hocuspocus: Hocuspocus;

  constructor(hocuspocus: Hocuspocus) {
    this.hocuspocus = hocuspocus;
  }

  @Post("/")
  @Middleware(requireSecretKey)
  convert(req: Request, res: Response) {
    const { page_id, name, description_html } = (req.body ?? {}) as Record<string, unknown>;
    if (typeof description_html !== "string") {
      res.status(400).json({ error: "description_html must be a string" });
      return;
    }
    try {
      const { binary, formats } = pageContent(description_html, typeof name === "string" ? name : undefined);
      const doc = typeof page_id === "string" ? this.hocuspocus.documents.get(page_id) : undefined;
      // shortcut: only the document on this live instance is replaced; with several live
      // replicas, the hocuspocus Redis extension relays the change to the others.
      if (doc) replaceDocument(doc, binary);
      res.json({
        description_binary: formats.contentBinaryEncoded,
        description_html: formats.contentHTML,
        description_json: formats.contentJSON,
        live: !!doc,
      });
    } catch (error) {
      logger.error("OCES_PAGE_CONTENT: conversion failed", error);
      res.status(500).json({ error: "Could not convert the page content" });
    }
  }
}
