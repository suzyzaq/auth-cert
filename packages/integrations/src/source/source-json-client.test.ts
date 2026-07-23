import { describe, expect, it } from "vitest";
import { SourceJsonClient } from "./source-json-client.js";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("SourceJsonClient", () => {
  it("rejects a brand mapped to the wrong shard", async () => {
    const fakeFetch: typeof fetch = async (input) => {
      const url = String(input);
      if (url.endsWith("/index.json")) {
        return jsonResponse({
          today: "2026-07-23",
          generated: "2026-07-23 13:59:18",
          shardCount: 2,
          brandCount: 1,
          brands: { 得力: 1 },
        });
      }
      if (url.endsWith("/shard/0.json")) {
        return jsonResponse({ 得力: { auth: [], cert: [] } });
      }
      if (url.endsWith("/shard/1.json")) return jsonResponse({});
      return jsonResponse({}, 404);
    };

    const client = new SourceJsonClient("https://example.test/api", fakeFetch);

    await expect(client.loadAll()).rejects.toThrow("brand shard mismatch");
  });

  it("loads a consistent source and checks the boundary shard", async () => {
    const requested: string[] = [];
    const fakeFetch: typeof fetch = async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.endsWith("/index.json")) {
        return jsonResponse({
          today: "2026-07-23",
          generated: "2026-07-23 13:59:18",
          shardCount: 1,
          brandCount: 1,
          brands: { 得力: 0 },
        });
      }
      if (url.endsWith("/shard/0.json")) {
        return jsonResponse({ 得力: { auth: [], cert: [] } });
      }
      return jsonResponse({}, 404);
    };

    const result = await new SourceJsonClient(
      "https://example.test/api",
      fakeFetch,
    ).loadAll();

    expect(result.brands).toHaveLength(1);
    expect(requested.at(-1)?.endsWith("/shard/1.json")).toBe(true);
  });
});
