export type SourceRecord = Record<string, unknown>;

export interface WritebackExecution {
  batchId: string;
  status: "SUCCEEDED" | "FAILED";
}

export interface SourceDatabase {
  currentVersion(): Promise<string>;
  findExecution(idempotencyKey: string): Promise<WritebackExecution | undefined>;
  transaction(work: () => Promise<void>): Promise<void>;
  update(recordId: string, field: string, value: unknown): Promise<void>;
  read(recordId: string): Promise<SourceRecord>;
  saveExecution(idempotencyKey: string, execution: WritebackExecution): Promise<void>;
}
