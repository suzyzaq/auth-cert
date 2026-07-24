import type {
  SourceDatabase,
  WritebackExecution,
} from "@auth-inspection/integrations/source-database";

export type WritebackField =
  | "name"
  | "type"
  | "level"
  | "grant"
  | "authed"
  | "enable"
  | "disable"
  | "flag"
  | "flagText"
  | "files";

export interface WritebackFinding {
  recordId: string;
  field: string;
  before: unknown;
  after: unknown;
  reviewed: boolean;
}

export interface WritebackBatch {
  id: string;
  idempotencyKey: string;
  sourceVersion: string;
  approvedBy: { id: string; role: "INSPECTOR" | "REVIEWER" | "ADMIN" };
  findings: WritebackFinding[];
}

interface Generator {
  build(): Promise<{ prefix: string; brandCount: number }>;
  validate(result: { prefix: string; brandCount: number }): Promise<void>;
}

interface Storage {
  promote(prefix: string): Promise<void>;
  discard(prefix: string): Promise<void>;
}

interface Dependencies {
  source: SourceDatabase;
  generator: Generator;
  storage: Storage;
}

const ALLOWED_FIELDS = new Set<WritebackField>([
  "name",
  "type",
  "level",
  "grant",
  "authed",
  "enable",
  "disable",
  "flag",
  "flagText",
  "files",
]);

export class WritebackService {
  constructor(private readonly dependencies: Dependencies) {}

  async execute(batch: WritebackBatch): Promise<WritebackExecution> {
    this.assertBatch(batch);

    const previous = await this.dependencies.source.findExecution(batch.idempotencyKey);
    if (previous) return previous;

    const version = await this.dependencies.source.currentVersion();
    if (version !== batch.sourceVersion) throw new Error("source data changed");

    await this.dependencies.source.transaction(async () => {
      for (const finding of batch.findings) {
        await this.dependencies.source.update(
          finding.recordId,
          finding.field,
          finding.after,
        );
        const updated = await this.dependencies.source.read(finding.recordId);
        if (!Object.is(updated[finding.field], finding.after)) {
          throw new Error(`write-back verification failed: ${finding.recordId}`);
        }
      }
    });

    const execution: WritebackExecution = { batchId: batch.id, status: "SUCCEEDED" };
    await this.dependencies.source.saveExecution(batch.idempotencyKey, execution);
    return execution;
  }

  async publishQueryData(): Promise<void> {
    let stagingPrefix: string | undefined;
    try {
      const result = await this.dependencies.generator.build();
      stagingPrefix = result.prefix;
      await this.dependencies.generator.validate(result);
      await this.dependencies.storage.promote(result.prefix);
    } catch (error) {
      if (stagingPrefix) await this.dependencies.storage.discard(stagingPrefix);
      throw error;
    }
  }

  private assertBatch(batch: WritebackBatch): void {
    if (!batch.idempotencyKey.trim()) throw new Error("idempotency key is required");
    if (batch.approvedBy.role !== "ADMIN") throw new Error("administrator approval required");
    if (batch.findings.length === 0) throw new Error("findings are required");
    if (batch.findings.some((finding) => !finding.reviewed)) {
      throw new Error("all findings must be reviewed");
    }
    const rejected = batch.findings.find(
      (finding) => !ALLOWED_FIELDS.has(finding.field as WritebackField),
    );
    if (rejected) throw new Error(`field is not allowed: ${rejected.field}`);
  }
}
