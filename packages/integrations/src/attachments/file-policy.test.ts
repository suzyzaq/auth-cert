import { describe, expect, it } from "vitest";
import { validateAttachment } from "./file-policy.js";

describe("validateAttachment", () => {
  it("rejects executable attachment content", () => {
    expect(() =>
      validateAttachment({
        mime: "application/x-msdownload",
        size: 40,
      }),
    ).toThrow("unsupported attachment type");
  });

  it("accepts a PDF within the size limit", () => {
    expect(
      validateAttachment({
        mime: "application/pdf",
        size: 2_000_000,
      }),
    ).toEqual({ mime: "application/pdf", size: 2_000_000 });
  });
});
