/**
 * Copyright (c) 2026-present Edwar Plata (oces) and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EventEmitter } from "events";
import { describe, expect, it, vi } from "vitest";
import { LiveHub, canReceive } from "@/oces/events.controller";

vi.mock("@/redis", () => ({ redisManager: { getClient: () => null } }));
vi.mock("@/env", () => ({ env: { API_BASE_URL: "http://api.test" } }));

class FakeSocket extends EventEmitter {
  OPEN = 1;
  readyState = 1;
  sent: string[] = [];
  closed: number | undefined;
  send(message: string) {
    this.sent.push(message);
  }
  ping() {}
  close(code: number) {
    this.closed = code;
    this.emit("close");
  }
}

const access = (byCookie: Record<string, string[]>) =>
  ({
    projectIds: vi.fn(async (_slug: string, cookie: string) => {
      if (!byCookie[cookie]) throw new Error("403");
      return byCookie[cookie];
    }),
  }) as never;

describe("live events hub", () => {
  it("only forwards events for the user's projects", async () => {
    const hub = new LiveHub(access({ a: ["p1"], b: ["p2"] }));
    const wsA = new FakeSocket();
    const wsB = new FakeSocket();
    await hub.add(wsA as never, "ws", "a");
    await hub.add(wsB as never, "ws", "b");

    hub.dispatch("oces:live:ws", JSON.stringify({ project_id: "p1", issue_id: "i1" }));
    hub.dispatch("oces:live:other", JSON.stringify({ project_id: "p1" }));

    expect(wsA.sent.slice(1)).toEqual([JSON.stringify({ project_id: "p1", issue_id: "i1" })]);
    expect(wsB.sent.slice(1)).toEqual([]);
    wsA.close(1000);
    wsB.close(1000);
  });

  it("refuses a cookie that is not a workspace member", async () => {
    const hub = new LiveHub(access({}));
    await expect(hub.add(new FakeSocket() as never, "ws", "nope")).rejects.toThrow();
  });

  it("sends workspace-level events to everyone", () => {
    expect(canReceive(new Set(), { project_id: null })).toBe(true);
    expect(canReceive(new Set(["p"]), { project_id: "q" })).toBe(false);
  });
});
