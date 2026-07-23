import type {
  AttachmentParser,
  ParsedDocument,
  ParseAttachmentInput,
} from "./contracts.js";

export class LocalFixtureParser implements AttachmentParser {
  constructor(
    private readonly fixtures: Record<string, ParsedDocument>,
  ) {}

  async parse(input: ParseAttachmentInput): Promise<ParsedDocument> {
    const fixture = this.fixtures[input.attachmentId];
    if (!fixture) throw new Error(`fixture not found: ${input.attachmentId}`);
    return structuredClone(fixture);
  }
}
