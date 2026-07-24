import { describe, expect, it, vi } from "vitest";
import { WritebackService } from "./writeback-service.js";

function makeBatch() {
  return {
    id: "batch-1",
    idempotencyKey: "writeback-20260723-1",
    sourceVersion: "v1",
    approvedBy: { id: "admin-1", role: "ADMIN" as const },
    findings: [
      {
        recordId: "record-1",
        field: "enable",
        before: "2032-09-07",
        after: "2022-09-07",
        reviewed: true,
      },
    ],
  };
}

function setup() {
  const source = {
    currentVersion: vi.fn().mockResolvedValue("v1"),
    findExecution: vi.fn().mockResolvedValue(undefined),
    transaction: vi.fn(async (work: () => Promise<void>) => {
      await work();
    }),
    update: vi.fn().mockResolvedValue(undefined),
    read: vi.fn().mockResolvedValue({ enable: "2022-09-07" }),
    saveExecution: vi.fn().mockResolvedValue(undefined),
  };
  const generator = {
    build: vi.fn().mockResolvedValue({ prefix: "staging/run-1", brandCount: 1 }),
    validate: vi.fn().mockResolvedValue(undefined),
  };
  const storage = {
    promote: vi.fn().mockResolvedValue(undefined),
    discard: vi.fn().mockResolvedValue(undefined),
  };
  return { source, generator, storage };
}

describe("WritebackService", () => {
  it("aborts when the source version changed", async () => {
    const deps = setup();
    deps.source.currentVersion.mockResolvedValue("v2");
    const service = new WritebackService(deps);

    await expect(service.execute(makeBatch())).rejects.toThrow("source data changed");
    expect(deps.source.update).not.toHaveBeenCalled();
  });

  it("rejects an unreviewed finding", async () => {
    const deps = setup();
    const service = new WritebackService(deps);
    const batch = makeBatch();
    batch.findings[0]!.reviewed = false;

    await expect(service.execute(batch)).rejects.toThrow("reviewed");
    expect(deps.source.transaction).not.toHaveBeenCalled();
  });

  it("reuses a completed idempotent execution", async () => {
    const deps = setup();
    deps.source.findExecution.mockResolvedValue({ batchId: "batch-1", status: "SUCCEEDED" });
    const service = new WritebackService(deps);

    await expect(service.execute(makeBatch())).resolves.toMatchObject({ status: "SUCCEEDED" });
    expect(deps.source.update).not.toHaveBeenCalled();
  });

  it("does not replace live shards when generation fails", async () => {
    const deps = setup();
    deps.generator.build.mockRejectedValue(new Error("invalid brand count"));
    const service = new WritebackService(deps);

    await expect(service.publishQueryData()).rejects.toThrow("invalid brand count");
    expect(deps.storage.promote).not.toHaveBeenCalled();
  });
});
