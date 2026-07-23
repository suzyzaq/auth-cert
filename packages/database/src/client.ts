import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Pool, type QueryResultRow } from "pg";

export interface DatabaseClient {
  query<T extends QueryResultRow>(
    text: string,
    values?: unknown[],
  ): Promise<{ rows: T[]; rowCount: number | null }>;
  migrate(): Promise<void>;
  resetForTests(): Promise<void>;
  close(): Promise<void>;
}

export function createDatabaseClient(databaseUrl: string): DatabaseClient {
  const pool = new Pool({ connectionString: databaseUrl, max: 4 });

  return {
    query: (text, values) => pool.query(text, values),
    async migrate() {
      const migrationPath = fileURLToPath(
        new URL("../migrations/0001_initial.sql", import.meta.url),
      );
      await pool.query(await readFile(migrationPath, "utf8"));
    },
    async resetForTests() {
      await pool.query(
        "TRUNCATE inspection_findings, audit_events, inspection_tasks CASCADE",
      );
    },
    async close() {
      await pool.end();
    },
  };
}
