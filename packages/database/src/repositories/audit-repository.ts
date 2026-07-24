import { randomUUID } from "node:crypto";
import type { DatabaseClient } from "../client.js";

export class AuditRepository {
  constructor(private readonly database: DatabaseClient) {}

  async append(input: {
    actorId: string;
    action: string;
    entityType: string;
    entityId: string;
    payload: Record<string, unknown>;
  }): Promise<void> {
    await this.database.query(
      `INSERT INTO audit_events
       (id, actor_id, action, entity_type, entity_id, payload)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        randomUUID(),
        input.actorId,
        input.action,
        input.entityType,
        input.entityId,
        input.payload,
      ],
    );
  }
}
