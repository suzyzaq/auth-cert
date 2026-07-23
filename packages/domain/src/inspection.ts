import { z } from "zod";

export const riskLevelSchema = z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]);
export type RiskLevel = z.infer<typeof riskLevelSchema>;

export const taskStatusSchema = z.enum([
  "QUEUED",
  "PARSING",
  "PARSE_FAILED",
  "INSPECTED",
  "REVIEW_REQUIRED",
  "REVIEWED",
  "AWAITING_WRITEBACK",
  "WRITING_BACK",
  "WRITTEN_BACK",
  "REJECTED",
]);
export type TaskStatus = z.infer<typeof taskStatusSchema>;

export const taskActionSchema = z.enum([
  "START_PARSE",
  "PARSE_SUCCESS",
  "PARSE_FAILURE",
  "REQUEST_REVIEW",
  "COMPLETE_REVIEW",
  "APPROVE",
  "REJECT",
  "START_WRITEBACK",
  "WRITEBACK_SUCCESS",
  "WRITEBACK_FAILURE",
]);
export type TaskAction = z.infer<typeof taskActionSchema>;

export const fieldEvidenceSchema = z.object({
  attachmentId: z.string().min(1),
  page: z.number().int().positive(),
  text: z.string().min(1),
  extractionMethod: z.enum(["OCR", "MODEL", "RULE", "HUMAN"]),
  confidence: z.number().min(0).max(1),
});
export type FieldEvidence = z.infer<typeof fieldEvidenceSchema>;

export const inspectionFieldSchema = z.object({
  field: z.string().min(1),
  sourceValue: z.unknown(),
  proposedValue: z.unknown(),
  confidence: z.number().min(0).max(1),
  risk: riskLevelSchema,
  errorCode: z.string().min(1),
  evidence: z.array(fieldEvidenceSchema).min(1),
  reviewReason: z.string().optional(),
});
export type InspectionField = z.infer<typeof inspectionFieldSchema>;

export const inspectionTaskSchema = z.object({
  id: z.string().uuid(),
  sourceRecordId: z.string().min(1),
  sourceVersion: z.string().min(1),
  status: taskStatusSchema,
  findings: z.array(inspectionFieldSchema),
});
export type InspectionTask = z.infer<typeof inspectionTaskSchema>;
