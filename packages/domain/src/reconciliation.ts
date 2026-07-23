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

export type CorrectionAction = "keep" | "update" | "fill" | "review";
export type ExtractionMethod = "OCR" | "MODEL" | "RULE" | "HUMAN";

export interface SourceAuthorizationFields {
  authorizationCode: string | null;
  authorizationType: string[];
  authorizationLevel: number | null;
  grantor: string | null;
  grantees: string[];
  brands: string[];
  categories: string[];
  region: string | null;
  effectiveDate: string | null;
  expiryDate: string | null;
  isProjectAuthorization: boolean | null;
  projectName: string | null;
  transferAllowed: boolean | null;
}

export interface AttachmentAuthorizationFields {
  authorizationCode: string | null;
  authorizationType: string[];
  authorizationLevel: number | null;
  grantor: string | null;
  grantees: string[];
  brandRaw: string[];
  brandStandard: string[];
  categoryRaw: string[];
  categoryStandard: string[];
  regionRaw: string | null;
  regionStandard: string | null;
  effectiveDate: string | null;
  expiryDate: string | null;
  isProjectAuthorization: boolean | null;
  projectName: string | null;
  transferAllowed: boolean | null;
}

export interface ReconciliationEvidence {
  attachmentId: string;
  attachmentUrl: string;
  field: string;
  page: number;
  text: string;
  extractionMethod: ExtractionMethod;
  confidence: number;
}

export interface FieldComparison {
  field: string;
  sourceValue: unknown;
  attachmentValue: unknown;
  correctedValue: unknown;
  comparisonStatus: ComparisonStatus;
  correctionAction: CorrectionAction;
  evidencePage: number | null;
  evidenceText: string;
  confidence: number;
}

export interface DataIssue {
  issueCode: string;
  severity: "critical" | "high" | "medium" | "low";
  field: string;
  description: string;
  suggestedAction: string;
}

export interface ReconciliationResult {
  taskStatus: "success" | "partial" | "failed";
  recordId: string;
  attachmentUrl: string;
  canAutoCorrect: boolean;
  manualReviewRequired: boolean;
  manualReviewReasons: string[];
  sourceFields: SourceAuthorizationFields;
  attachmentFields: AttachmentAuthorizationFields;
  correctionFields: Partial<SourceAuthorizationFields>;
  fieldComparisons: FieldComparison[];
  dataIssues: DataIssue[];
  evidenceSummary: ReconciliationEvidence[];
}

export interface ReconcileAuthorizationInput {
  recordId: string;
  attachmentUrl: string;
  source: SourceAuthorizationFields;
  attachment: AttachmentAuthorizationFields;
  evidence: ReconciliationEvidence[];
  parseStatus?: "SUCCESS" | "UNCLEAR" | "FAILED" | "CONFLICT";
}

type ComparableField = {
  field: string;
  sourceValue: unknown;
  attachmentValue: unknown;
};

function normalizeDate(value: string | null): string | null {
  if (!value) return null;
  const matched = value
    .trim()
    .match(/^(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?$/);
  if (!matched) return value.trim();
  return `${matched[1]}-${matched[2]!.padStart(2, "0")}-${matched[3]!.padStart(2, "0")}`;
}

function isMissing(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

function equalValues(left: unknown, right: unknown): boolean {
  if (Array.isArray(left) && Array.isArray(right)) {
    return JSON.stringify([...left].sort()) === JSON.stringify([...right].sort());
  }
  return left === right;
}

function comparison(
  item: ComparableField,
  evidence: ReconciliationEvidence[],
  parseStatus: ReconcileAuthorizationInput["parseStatus"],
): FieldComparison {
  const proof = evidence.find((entry) => entry.field === item.field);
  let comparisonStatus: ComparisonStatus;
  let correctionAction: CorrectionAction;

  if (parseStatus === "FAILED" || parseStatus === "UNCLEAR") {
    comparisonStatus = "ATTACHMENT_UNCLEAR";
    correctionAction = "review";
  } else if (parseStatus === "CONFLICT") {
    comparisonStatus = "ATTACHMENT_CONFLICT";
    correctionAction = "review";
  } else if (item.field === "authorizationLevel" && isMissing(item.attachmentValue)) {
    comparisonStatus = "CHAIN_INCOMPLETE";
    correctionAction = "review";
  } else if (isMissing(item.attachmentValue)) {
    comparisonStatus = "ATTACHMENT_FIELD_MISSING";
    correctionAction = "review";
  } else if (isMissing(item.sourceValue)) {
    comparisonStatus = "SOURCE_FIELD_MISSING";
    correctionAction = "fill";
  } else if (equalValues(item.sourceValue, item.attachmentValue)) {
    comparisonStatus = "CONSISTENT";
    correctionAction = "keep";
  } else {
    comparisonStatus = "SOURCE_FIELD_ERROR";
    correctionAction = "update";
  }

  return {
    ...item,
    correctedValue:
      correctionAction === "review" ? null : item.attachmentValue,
    comparisonStatus,
    correctionAction,
    evidencePage: proof?.page ?? null,
    evidenceText: proof?.text ?? "",
    confidence: proof?.confidence ?? 0,
  };
}

export function reconcileAuthorization(
  input: ReconcileAuthorizationInput,
): ReconciliationResult {
  const { source, attachment } = input;
  const fields: ComparableField[] = [
    {
      field: "authorizationCode",
      sourceValue: source.authorizationCode,
      attachmentValue: attachment.authorizationCode,
    },
    {
      field: "authorizationType",
      sourceValue: source.authorizationType,
      attachmentValue: attachment.authorizationType,
    },
    {
      field: "authorizationLevel",
      sourceValue: source.authorizationLevel,
      attachmentValue: attachment.authorizationLevel,
    },
    { field: "grantor", sourceValue: source.grantor, attachmentValue: attachment.grantor },
    { field: "grantees", sourceValue: source.grantees, attachmentValue: attachment.grantees },
    { field: "brands", sourceValue: source.brands, attachmentValue: attachment.brandStandard },
    {
      field: "categories",
      sourceValue: source.categories,
      attachmentValue: attachment.categoryStandard,
    },
    {
      field: "region",
      sourceValue: source.region,
      attachmentValue: attachment.regionStandard,
    },
    {
      field: "effectiveDate",
      sourceValue: normalizeDate(source.effectiveDate),
      attachmentValue: normalizeDate(attachment.effectiveDate),
    },
    {
      field: "expiryDate",
      sourceValue: normalizeDate(source.expiryDate),
      attachmentValue: normalizeDate(attachment.expiryDate),
    },
    {
      field: "isProjectAuthorization",
      sourceValue: source.isProjectAuthorization,
      attachmentValue: attachment.isProjectAuthorization,
    },
    {
      field: "projectName",
      sourceValue: source.projectName,
      attachmentValue: attachment.projectName,
    },
    {
      field: "transferAllowed",
      sourceValue: source.transferAllowed,
      attachmentValue: attachment.transferAllowed,
    },
  ];

  const fieldComparisons = fields.map((item) =>
    comparison(item, input.evidence, input.parseStatus),
  );
  const dataIssues: DataIssue[] = [];

  if (
    attachment.isProjectAuthorization === true &&
    source.isProjectAuthorization !== true
  ) {
    dataIssues.push({
      issueCode: "PROJECT_AUTHORIZATION_MISSING",
      severity: "high",
      field: "isProjectAuthorization",
      description: "附件明确限定项目，但现存字段未标记为项目授权",
      suggestedAction: "按附件补充项目授权标记和项目名称",
    });
  }
  if (
    source.categories.includes("全品类") &&
    attachment.categoryStandard.length > 0 &&
    !attachment.categoryStandard.includes("全品类")
  ) {
    dataIssues.push({
      issueCode: "CATEGORY_SCOPE_OVERSTATED",
      severity: "high",
      field: "categories",
      description: "现存字段为全品类，但附件仅授权指定品类",
      suggestedAction: "收窄为附件明确列出的标准品类",
    });
  }
  if (
    source.authorizationCode &&
    attachment.authorizationCode &&
    source.authorizationCode !== attachment.authorizationCode
  ) {
    dataIssues.push({
      issueCode: "AUTHORIZATION_CODE_MISMATCH",
      severity: "critical",
      field: "authorizationCode",
      description: "附件编号与现存授权编码不一致",
      suggestedAction: "检查附件是否挂错记录",
    });
  }

  const manualReviewReasons: string[] = [];
  if (attachment.authorizationLevel === null) {
    manualReviewReasons.push("授权链不完整，无法确定授权层级");
  }
  for (const item of fieldComparisons) {
    if (
      item.comparisonStatus === "ATTACHMENT_UNCLEAR" ||
      item.comparisonStatus === "ATTACHMENT_CONFLICT"
    ) {
      manualReviewReasons.push(`${item.field} 的附件证据需要人工确认`);
    }
  }
  const hasHighRisk = dataIssues.some(
    (item) => item.severity === "critical" || item.severity === "high",
  );
  const allCorrectionsSupported = fieldComparisons
    .filter((item) => item.correctionAction === "update" || item.correctionAction === "fill")
    .every((item) => item.confidence >= 0.9 && item.evidencePage !== null);
  const manualReviewRequired =
    manualReviewReasons.length > 0 ||
    fieldComparisons.some((item) => item.correctionAction === "review");

  const correctionFields: Partial<SourceAuthorizationFields> = {};
  for (const item of fieldComparisons) {
    if (item.correctionAction === "update" || item.correctionAction === "fill") {
      (correctionFields as Record<string, unknown>)[item.field] =
        item.correctedValue;
    }
  }

  return {
    taskStatus: input.parseStatus === "FAILED" ? "failed" : manualReviewRequired ? "partial" : "success",
    recordId: input.recordId,
    attachmentUrl: input.attachmentUrl,
    canAutoCorrect:
      !manualReviewRequired && !hasHighRisk && allCorrectionsSupported,
    manualReviewRequired,
    manualReviewReasons: [...new Set(manualReviewReasons)],
    sourceFields: source,
    attachmentFields: attachment,
    correctionFields,
    fieldComparisons,
    dataIssues,
    evidenceSummary: input.evidence,
  };
}
