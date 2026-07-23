import { describe, expect, it, vi } from "vitest";
import { SessionService } from "./session.js";

describe("SessionService", () => {
  it("maps disabled DingTalk users to a denied session", async () => {
    const dingtalk = {
      exchangeCode: vi.fn().mockResolvedValue({ accessToken: "token" }),
      getUser: vi.fn().mockResolvedValue({
        unionId: "union-1",
        name: "停用用户",
        active: false,
      }),
    };
    const roles = { findByUnionId: vi.fn() };
    const session = new SessionService(dingtalk, roles);

    await expect(session.create("temporary-code")).rejects.toThrow(
      "organization account disabled",
    );
    expect(roles.findByUnionId).not.toHaveBeenCalled();
  });

  it("creates a secure reviewer session with a csrf token", async () => {
    const dingtalk = {
      exchangeCode: vi.fn().mockResolvedValue({ accessToken: "token" }),
      getUser: vi.fn().mockResolvedValue({
        unionId: "union-1",
        name: "张复核",
        active: true,
      }),
    };
    const roles = {
      findByUnionId: vi.fn().mockResolvedValue({ role: "REVIEWER" }),
    };
    const session = new SessionService(dingtalk, roles);

    await expect(session.create("temporary-code")).resolves.toMatchObject({
      user: { name: "张复核", role: "REVIEWER" },
      cookie: { httpOnly: true, secure: true, sameSite: "strict" },
    });
  });
});
