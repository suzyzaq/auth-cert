import type {
  AttachmentParser,
  ParsedDocument,
  ParseAttachmentInput,
} from "./contracts.js";

export class MultimodalGateway implements AttachmentParser {
  constructor(private readonly endpoint?: string) {}

  async parse(_input: ParseAttachmentInput): Promise<ParsedDocument> {
    if (!this.endpoint) {
      throw new Error("multimodal gateway is not configured");
    }
    throw new Error("multimodal adapter requires production credentials");
  }
}
