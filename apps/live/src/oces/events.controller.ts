/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Live updates: forwards "something changed" events (ids only) from Redis to browsers.
// The API publishes them on `oces:live:<workspace slug>` (apps/api/plane/oces/live.py).
// Each socket only gets events for projects its user belongs to; the browser then
// re-fetches through the normal API, which applies all other permissions.

import type { Request } from "express";
import type Redis from "ioredis";
import type { WebSocket } from "ws";
import { Controller, WebSocket as WSDecorator } from "@plane/decorators";
import { logger } from "@plane/logger";
import { redisManager } from "@/redis";
import { APIService } from "@/services/api.service";

const SLUG = /^[a-z0-9_-]{1,64}$/i;
const PING_MS = 30_000;
const ACCESS_REFRESH_MS = 60_000;
const ACCESS_RECHECK_MIN_MS = 10_000;

export type LiveEvent = { project_id?: string | null; [key: string]: unknown };

type Conn = {
  ws: WebSocket;
  cookie: string;
  slug: string;
  projects: Set<string>;
  checkedAt: number;
};

class AccessService extends APIService {
  async projectIds(slug: string, cookie: string): Promise<string[]> {
    const res = await this.get(`/api/workspaces/${slug}/oces/live-access/`, { headers: { Cookie: cookie } });
    return res.data.project_ids as string[];
  }
}

/** Whether this connection may receive the event. Workspace-level events (no project) go to everyone. */
export const canReceive = (projects: Set<string>, event: LiveEvent) =>
  !event.project_id || projects.has(event.project_id);

export class LiveHub {
  private conns = new Map<string, Set<Conn>>();
  private subscriber: Redis | null = null;
  constructor(private access = new AccessService()) {}

  private getSubscriber(): Redis | null {
    if (this.subscriber) return this.subscriber;
    const client = redisManager.getClient();
    if (!client) return null;
    this.subscriber = client.duplicate();
    this.subscriber.on("message", (channel: string, message: string) => this.dispatch(channel, message));
    return this.subscriber;
  }

  async add(ws: WebSocket, slug: string, cookie: string) {
    const conn: Conn = { ws, slug, cookie, projects: new Set(), checkedAt: 0 };
    await this.refresh(conn); // throws when the cookie is not a member of the workspace
    let set = this.conns.get(slug);
    if (!set) {
      set = new Set();
      this.conns.set(slug, set);
      await this.getSubscriber()?.subscribe(`oces:live:${slug}`);
    }
    set.add(conn);

    const ping = setInterval(() => ws.readyState === ws.OPEN && ws.ping(), PING_MS);
    const recheck = setInterval(() => this.refresh(conn).catch(() => ws.close(4403, "forbidden")), ACCESS_REFRESH_MS);
    ws.on("close", () => {
      clearInterval(ping);
      clearInterval(recheck);
      set.delete(conn);
      if (set.size === 0) {
        this.conns.delete(slug);
        this.subscriber?.unsubscribe(`oces:live:${slug}`).catch(() => undefined);
      }
    });
    ws.send(JSON.stringify({ action: "ready" }));
  }

  private async refresh(conn: Conn) {
    conn.checkedAt = Date.now();
    conn.projects = new Set(await this.access.projectIds(conn.slug, conn.cookie));
  }

  dispatch(channel: string, message: string) {
    const set = this.conns.get(channel.slice("oces:live:".length));
    if (!set) return;
    let event: LiveEvent;
    try {
      event = JSON.parse(message) as LiveEvent;
    } catch {
      return;
    }
    for (const conn of set) {
      if (canReceive(conn.projects, event)) {
        conn.ws.send(message);
      } else if (Date.now() - conn.checkedAt > ACCESS_RECHECK_MIN_MS) {
        // maybe just added to that project: re-check, then deliver if allowed now
        this.refresh(conn)
          .then(() => canReceive(conn.projects, event) && conn.ws.send(message))
          .catch(() => conn.ws.close(4403, "forbidden"));
      }
    }
  }
}

const hub = new LiveHub();

@Controller("/oces")
export class OcesEventsController {
  [key: string]: unknown;

  @WSDecorator("/events")
  async handleConnection(ws: WebSocket, req: Request) {
    const slug = String(req.query.workspaceSlug ?? "");
    const cookie = req.headers.cookie ?? "";
    if (!SLUG.test(slug) || !cookie) {
      ws.close(4400, "bad request");
      return;
    }
    ws.on("error", (error: Error) => logger.error("OCES_EVENTS: socket error", error));
    try {
      await hub.add(ws, slug, cookie);
    } catch {
      ws.close(4403, "forbidden");
    }
  }
}
