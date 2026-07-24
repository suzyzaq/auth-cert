import { describe, expect, it, vi } from "vitest";
import { WritebackService } from "../../apps/api/src/writeback/writeback-service.js";

function dependencies() {
  return {
    source: {
      currentVersion: vi.fn().mockResolvedValue("v1"),
      findExecution: vi.fn().mockResolvedValue(undefined),
      transaction: vi.fn(async (work: () => Promise<void>) => {
        await work();
      }),
      update: vi.fn().mockResolvedValue(undefined),
      read: vi.fn().mockResolvedValue({ enable: "2022-09-07" }),
      saveExecution: vi.fn().mockResolvedValue(undefined),
    },
    generator: {
      build: vi.fn().mockResolvedValue({ prefix: "staging/1", brandCount: 1 }),
      validate: vi.fn().mockResolvedValue(undefined),
    },
    storage: {
      promote: vi.fn().mockResolvedValue(undefined),
      discard: vi.fn().mockResolvedValue(undefined),
    },
  };
}

describe("write-back production barriers", () => {
  it("blocks reviewer approval and unsupported fields", async () => {
    const deps = dependencies();
    const service = new WritebackService(deps);

    await expect(
      service.execute({
        id: "batch-1",
        idempotencyKey: "key-1",
        sourceVersion: "v1",
        approvedBy: { id: "reviewer-1", role: "REVIEWER" },
        findings: [
          {
            recordId: "record-1",
            field: "rawSystemFlag",
            before: false,
            after: true,
            reviewed: true,
          },
        ],
      }),
    ).rejects.toThrow("administrator approval required");
    expect(deps.source.update).not.toHaveBeenCalled();
  });

  it("blocks a stale source version before opening a transaction", async () => {
    const deps = dependencies();
    deps.source.currentVersion.mockResolvedValue("v2");
    const service = new WritebackService(deps);

    await expect(
      service.execute({
        id: "batch-1",
        idempotencyKey: "key-1",
        sourceVersion: "v1",
        approvedBy: { id: "admin-1", role: "ADMIN" },
        findings: [
          {
            recordId: "record-1",
            field: "enable",
            before: "2032-09-07",
            after: "2022-09-07",
            reviewed: true,
          },
        ],
      }),
    ).rejects.toThrow("source data changed");
    expect(deps.source.transaction).not.toHaveBeenCalled();
  });
});

