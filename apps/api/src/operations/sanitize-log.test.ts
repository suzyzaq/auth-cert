import { describe, expect, it } from "vitest";
import { sanitizeLog } from "./sanitize-log.js";

describe("sanitizeLog", () => {
  it("redacts tokens and signed URL query strings", () => {
    expect(
      sanitizeLog({
        token: "secret",
        nested: { authorization: "Bearer secret" },
        url: "https://oss.example/a.pdf?Signature=secret&Expires=123",
      }),
    ).toEqual({
      token: "[REDACTED]",
      nested: { authorization: "[REDACTED]" },
      url: "https://oss.example/a.pdf",
    });
  });

  it("keeps ordinary values available for diagnosis", () => {
    expect(sanitizeLog({ traceId: "trace-1", status: "ok", count: 12 })).toEqual({
      traceId: "trace-1",
      status: "ok",
      count: 12,
    });
  });
});
