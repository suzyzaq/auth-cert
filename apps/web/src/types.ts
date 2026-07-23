export type Risk = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface InspectionTask {
  id: string;
  brand: string;
  code: string;
  name: string;
  status: string;
  risk: Risk;
  issueCount: number;
  assignee: string;
  updatedAt: string;
}

export type ComparisonStatus =
  | "CONSISTENT"
  | "SOURCE_FIELD_ERROR"
  | "SOURCE_FIELD_MISSING"
  | "ATTACHMENT_FIELD_MISSING"
  | "ATTACHMENT_UNCLEAR"
  | "ATTACHMENT_CONFLICT"
  | "SKILL_MATCH_UNCERTAIN"
  | "CHAIN_INCOMPLETE"
  | "MANUAL_REVIEW_REQUIRED";

export interface ReviewComparison {
  field: string;
  label: string;
  sourceValue: string | null;
  attachmentValue: string | null;
  correctedValue: string | null;
  comparisonStatus: ComparisonStatus;
  action: "keep" | "update" | "fill" | "review";
  evidencePage: number | null;
  evidenceText: string;
  confidence: number;
}

export interface EvidenceReview {
  taskId: string;
  attachmentTitle: string;
  attachmentPages: number;
  attachmentUrl: string;
  documentNumber: string;
  documentBody: string[];
  overallConfidence: number;
  canAutoCorrect: boolean;
  manualReviewReasons: string[];
  comparisons: ReviewComparison[];
}
