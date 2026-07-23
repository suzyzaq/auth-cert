import type {
  AttachmentParser,
  ExtractedField,
} from "@auth-inspection/integrations/parsing";

export interface InspectionJob {
  taskId: string;
  attachmentId: string;
  mime: string;
  bytes: Uint8Array;
}

export interface WorkerRepository {
  saveFindings(taskId: string, fields: ExtractedField[]): Promise<void>;
  transition(
    taskId: string,
    status: "INSPECTED" | "REVIEW_REQUIRED",
  ): Promise<void>;
}

export async function processInspection(
  job: InspectionJob,
  dependencies: {
    parser: AttachmentParser;
    repository: WorkerRepository;
  },
): Promise<void> {
  const parsed = await dependencies.parser.parse({
    attachmentId: job.attachmentId,
    mime: job.mime,
    bytes: job.bytes,
  });

  await dependencies.repository.saveFindings(job.taskId, parsed.fields);
  const requiresReview = parsed.fields.some(
    (item) => item.confidence < 0.85 || item.value === null,
  );
  await dependencies.repository.transition(
    job.taskId,
    requiresReview ? "REVIEW_REQUIRED" : "INSPECTED",
  );
}
