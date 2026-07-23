export type ExtractionMethod = "OCR" | "MODEL" | "RULE" | "HUMAN";

export interface ExtractedField {
  name: string;
  value: string | null;
  confidence: number;
  method: ExtractionMethod;
  page?: number;
  evidenceText?: string;
  validationStatus?: "SINGLE_SOURCE" | "CONFIRMED" | "CONFLICT";
  errorCode?: "EVIDENCE_CONFLICT";
  evidence?: ExtractedField[];
}

export interface ParsedDocument {
  pages: number;
  fields: ExtractedField[];
  rawText: string;
}

export interface ParseAttachmentInput {
  attachmentId: string;
  mime: string;
  bytes: Uint8Array;
}

export interface AttachmentParser {
  parse(input: ParseAttachmentInput): Promise<ParsedDocument>;
}

export function field(
  name: string,
  value: string | null,
  confidence: number,
  method: ExtractionMethod,
): ExtractedField {
  return { name, value, confidence, method };
}

export function crossValidate(
  left: ExtractedField,
  right: ExtractedField,
):
  | {
      status: "CONFIRMED";
      value: string | null;
      confidence: number;
      errorCode: null;
    }
  | {
      status: "REVIEW_REQUIRED";
      value: null;
      confidence: number;
      errorCode: "EVIDENCE_CONFLICT";
    } {
  if (left.name !== right.name || left.value !== right.value) {
    return {
      status: "REVIEW_REQUIRED",
      value: null,
      confidence: Math.min(left.confidence, right.confidence),
      errorCode: "EVIDENCE_CONFLICT",
    };
  }
  return {
    status: "CONFIRMED",
    value: left.value,
    confidence: Math.min(left.confidence, right.confidence),
    errorCode: null,
  };
}
