import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildApp } from "../app.js";

const app = buildApp();

beforeAll(() => app.ready());
afterAll(() => app.close());

describe("API security controls", () => {
  it("adds a trace id and restrictive browser headers", async () => {
    const response = await app.inject({ method: "GET", url: "/health" });

    expect(response.headers["x-trace-id"]).toBeTruthy();
    expect(response.headers["x-content-type-options"]).toBe("nosniff");
    expect(response.headers["content-security-policy"]).toContain("default-src 'none'");
  });

  it("rejects oversized request bodies", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/reviews",
      headers: { "content-type": "application/json" },
      payload: JSON.stringify({ note: "x".repeat(1_100_000) }),
    });

    expect(response.statusCode).toBe(413);
  });
});
