import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildApp } from "../app.js";

describe("task routes", () => {
  const app = buildApp();

  beforeAll(() => app.ready());
  afterAll(() => app.close());

  it("returns paginated inspection tasks", async () => {
    const response = await app.inject({
      method: "GET",
      url: "/api/tasks?risk=CRITICAL",
      headers: { "x-user-role": "INSPECTOR" },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({
      total: expect.any(Number),
      items: expect.any(Array),
    });
  });

  it("rejects write-back approval by an inspector", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/api/writebacks/batch-1/approve",
      headers: { "x-user-role": "INSPECTOR" },
    });

    expect(response.statusCode).toBe(403);
  });
});
