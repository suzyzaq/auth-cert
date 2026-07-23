import type {
  AttachmentParser,
  ExtractedField,
} from "@auth-inspection/integrations/parsing";
import {
  reconcileAuthorization,
  type AttachmentAuthorizationFields,
  type ReconciliationResult,
  type SourceAuthorizationFields,
} from "@auth-inspection/domain";

export interface InspectionJob {
  taskId: string;
  attachmentId: string;
  attachmentUrl?: string;
  mime: string;
  bytes: Uint8Array;
  sourceFields?: SourceAuthorizationFields;
}

export interface WorkerRepository {
  saveFindings(taskId: string, fields: ExtractedField[]): Promise<void>;
  saveReconciliation?(
    taskId: string,
    result: ReconciliationResult,
  ): Promise<void>;
  transition(
    taskId: string,
    status: "INSPECTED" | "REVIEW_REQUIRED",
  ): Promise<void>;
}

function value(fields: ExtractedField[], name: string): string | null {
  return fields.find((item) => item.name === name)?.value ?? null;
}

function values(fields: ExtractedField[], name: string): string[] {
  const raw = value(fields, name);
  return raw
    ? raw
        .split(/[、,，;；]/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
}

function numericValue(fields: ExtractedField[], name: string): number | null {
  const raw = value(fields, name);
  if (!raw) return null;
  const parsed = Number.parseInt(raw.replace(/\D/g, ""), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function booleanValue(
  fields: ExtractedField[],
  name: string,
): boolean | null {
  const raw = value(fields, name);
  if (!raw) return null;
  if (["是", "允许", "true"].includes(raw.toLowerCase())) return true;
  if (["否", "不允许", "false"].includes(raw.toLowerCase())) return false;
  return null;
}

function rebuildAttachmentFields(
  fields: ExtractedField[],
): AttachmentAuthorizationFields {
  const brandRaw = values(fields, "brand");
  const categoryRaw = values(fields, "category");
  const regionRaw = value(fields, "region");
  return {
    authorizationCode: value(fields, "authorizationCode"),
    authorizationType: values(fields, "authorizationType"),
    authorizationLevel: numericValue(fields, "authorizationLevel"),
    grantor: value(fields, "grantor"),
    grantees: values(fields, "grantees"),
    brandRaw,
    brandStandard: values(fields, "brandStandard").length
      ? values(fields, "brandStandard")
      : brandRaw,
    categoryRaw,
    categoryStandard: values(fields, "categoryStandard").length
      ? values(fields, "categoryStandard")
      : categoryRaw,
    regionRaw,
    regionStandard: value(fields, "regionStandard") ?? regionRaw,
    effectiveDate: value(fields, "effectiveDate"),
    expiryDate: value(fields, "expiryDate"),
    isProjectAuthorization: booleanValue(fields, "isProjectAuthorization"),
    projectName: value(fields, "projectName"),
    transferAllowed: booleanValue(fields, "transferAllowed"),
  };
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
    ...(job.attachmentUrl ? { sourceUrl: job.attachmentUrl } : {}),
    mime: job.mime,
    bytes: job.bytes,
  });

  await dependencies.repository.saveFindings(job.taskId, parsed.fields);
  if (
    job.sourceFields &&
    job.attachmentUrl &&
    dependencies.repository.saveReconciliation
  ) {
    const evidence = parsed.fields
      .filter(
        (item) =>
          item.page !== undefined &&
          item.evidenceText !== undefined &&
          item.evidenceText.length > 0,
      )
      .map((item) => ({
        attachmentId: job.attachmentId,
        attachmentUrl: job.attachmentUrl!,
        field: item.name,
        page: item.page!,
        text: item.evidenceText!,
        extractionMethod: item.method,
        confidence: item.confidence,
      }));
    const parseStatus = parsed.fields.some(
      (item) => item.validationStatus === "CONFLICT",
    )
      ? "CONFLICT"
      : undefined;
    const result = reconcileAuthorization({
      recordId: job.taskId,
      attachmentUrl: job.attachmentUrl,
      source: job.sourceFields,
      attachment: rebuildAttachmentFields(parsed.fields),
      evidence,
      ...(parseStatus ? { parseStatus } : {}),
    });
    await dependencies.repository.saveReconciliation(job.taskId, result);
  }
  const requiresReview = parsed.fields.some(
    (item) =>
      item.confidence < 0.85 ||
      item.value === null ||
      item.validationStatus === "CONFLICT",
  );
  await dependencies.repository.transition(
    job.taskId,
    requiresReview ? "REVIEW_REQUIRED" : "INSPECTED",
  );
}
