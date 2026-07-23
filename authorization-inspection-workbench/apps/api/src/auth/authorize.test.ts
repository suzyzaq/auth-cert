import { describe, expect, it } from "vitest";
import { authorize } from "./authorize.js";

describe("authorize", () => {
  it("prevents inspectors from approving write-back", () => {
    expect(() => authorize("INSPECTOR", "APPROVE_WRITEBACK")).toThrow(
      "forbidden",
    );
  });

  it("allows administrators to approve write-back", () => {
    expect(authorize("ADMIN", "APPROVE_WRITEBACK")).toBe(true);
  });
});
