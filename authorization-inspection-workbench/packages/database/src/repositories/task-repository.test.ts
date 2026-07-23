import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createDatabaseClient } from "../client.js";
import { PostgresTaskRepository } from "./task-repository.js";

const databaseUrl =
  process.env.DATABASE_URL ??
  "postgresql://auth_inspection:auth_inspection@localhost:5432/auth_inspection";

describe("PostgresTaskRepository", () => {
  const client = createDatabaseClient(databaseUrl);
  const repository = new PostgresTaskRepository(client);

  beforeAll(async () => {
    await client.migrate();
    await client.resetForTests();
  });

  afterAll(async () => {
    await client.close();
  });

  it("keeps source snapshots immutable", async () => {
    const task = await repository.createTask({
      sourceRecordId: "26062914254888",
      sourceVersion: "2026-07-23T13:59:18",
      brand: "BABYCARE",
      sourcePayload: {
        enable: "2032-09-07",
        disable: "2022-09-06",
      },
    });

    await expect(
      repository.replaceSourceSnapshot(task.id, {
        enable: "2022-09-07",
        disable: "2032-09-06",
      }),
    ).rejects.toThrow("source snapshot is immutable");
  });

  it("does not create two active tasks for one source version", async () => {
    const input = {
      sourceRecordId: "26071319475337",
      sourceVersion: "2026-07-23T13:59:18",
      brand: "印芭贝",
      sourcePayload: {},
    };

    const first = await repository.createTask(input);
    const second = await repository.createTask(input);

    expect(second.id).toBe(first.id);
  });
});
