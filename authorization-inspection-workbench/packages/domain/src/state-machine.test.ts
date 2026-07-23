import { describe, expect, it } from "vitest";
import { transitionTask } from "./state-machine.js";

describe("inspection task state", () => {
  it("requires review before approval", () => {
    expect(() => transitionTask("INSPECTED", "APPROVE")).toThrow(
      "review required",
    );
  });

  it("allows a reviewed task to await write-back", () => {
    expect(transitionTask("REVIEWED", "APPROVE")).toBe(
      "AWAITING_WRITEBACK",
    );
  });

  it("rejects unknown transitions", () => {
    expect(() => transitionTask("WRITTEN_BACK", "START_PARSE")).toThrow(
      "transition not allowed",
    );
  });
});
