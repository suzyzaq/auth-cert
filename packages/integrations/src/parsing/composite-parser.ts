import type {
  AttachmentParser,
  ExtractedField,
  ParsedDocument,
  ParseAttachmentInput,
} from "./contracts.js";

function singleSource(field: ExtractedField): ExtractedField {
  return {
    ...field,
    validationStatus: "SINGLE_SOURCE",
    evidence: [field],
  };
}

function mergeField(
  left: ExtractedField | undefined,
  right: ExtractedField | undefined,
): ExtractedField {
  if (!left) return singleSource(right!);
  if (!right) return singleSource(left);
  if (left.value !== right.value) {
    return {
      name: left.name,
      value: null,
      confidence: Math.min(left.confidence, right.confidence),
      method: "RULE",
      validationStatus: "CONFLICT",
      errorCode: "EVIDENCE_CONFLICT",
      evidence: [left, right],
    };
  }
  return {
    name: left.name,
    value: left.value,
    confidence: Math.min(left.confidence, right.confidence),
    method: "RULE",
    ...(left.page !== undefined ? { page: left.page } : {}),
    ...(left.evidenceText !== undefined
      ? { evidenceText: left.evidenceText }
      : {}),
    validationStatus: "CONFIRMED",
    evidence: [left, right],
  };
}

export class CompositeAttachmentParser implements AttachmentParser {
  constructor(
    private readonly ocr: AttachmentParser,
    private readonly model: AttachmentParser,
  ) {}

  async parse(input: ParseAttachmentInput): Promise<ParsedDocument> {
    const [ocrResult, modelResult] = await Promise.all([
      this.ocr.parse(input),
      this.model.parse(input),
    ]);
    const names = new Set([
      ...ocrResult.fields.map((field) => field.name),
      ...modelResult.fields.map((field) => field.name),
    ]);
    const fields = [...names].map((name) =>
      mergeField(
        ocrResult.fields.find((field) => field.name === name),
        modelResult.fields.find((field) => field.name === name),
      ),
    );

    return {
      pages: Math.max(ocrResult.pages, modelResult.pages),
      fields,
      rawText: [ocrResult.rawText, modelResult.rawText]
        .filter(Boolean)
        .join("\n\n"),
    };
  }
}
