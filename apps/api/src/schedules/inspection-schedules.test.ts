import { describe, expect, it } from "vitest";
import {
  inspectionSchedule,
  scheduledBatchKey,
} from "./inspection-schedules.js";

describe("inspection schedules", () => {
  it("schedules incremental inspection after the source refresh", () => {
    expect(inspectionSchedule.incremental).toBe("30 17 * * 1-5");
    expect(inspectionSchedule.full).toBe("0 2 * * 0");
  });

  it("creates stable idempotency keys for the same schedule window", () => {
    const time = new Date("2026-07-23T17:30:00+08:00");
    expect(scheduledBatchKey("incremental", time)).toBe(
      scheduledBatchKey("incremental", time),
    );
    expect(scheduledBatchKey("incremental", time)).not.toBe(
      scheduledBatchKey("full", time),
    );
  });
});
