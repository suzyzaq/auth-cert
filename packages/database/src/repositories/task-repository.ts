import { randomUUID } from "node:crypto";
import type { DatabaseClient } from "../client.js";
import type { InspectionTaskRow, NewInspectionTask } from "../schema.js";

interface TaskDbRow {
  id: string;
  source_record_id: string;
  source_version: string;
  brand: string;
  status: string;
  source_payload: Record<string, unknown>;
  created_at: Date;
  updated_at: Date;
}

function mapTask(row: TaskDbRow): InspectionTaskRow {
  return {
    id: row.id,
    sourceRecordId: row.source_record_id,
    sourceVersion: row.source_version,
    brand: row.brand,
    status: row.status,
    sourcePayload: row.source_payload,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export class PostgresTaskRepository {
  constructor(private readonly database: DatabaseClient) {}

  async createTask(input: NewInspectionTask): Promise<InspectionTaskRow> {
    const result = await this.database.query<TaskDbRow>(
      `INSERT INTO inspection_tasks
        (id, source_record_id, source_version, brand, source_payload)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (source_record_id, source_version)
       DO UPDATE SET source_record_id = EXCLUDED.source_record_id
       RETURNING *`,
      [
        randomUUID(),
        input.sourceRecordId,
        input.sourceVersion,
        input.brand,
        input.sourcePayload,
      ],
    );

    const row = result.rows[0];
    if (!row) throw new Error("task creation returned no row");
    return mapTask(row);
  }

  async replaceSourceSnapshot(
    _taskId: string,
    _sourcePayload: Record<string, unknown>,
  ): Promise<never> {
    throw new Error("source snapshot is immutable");
  }
}
