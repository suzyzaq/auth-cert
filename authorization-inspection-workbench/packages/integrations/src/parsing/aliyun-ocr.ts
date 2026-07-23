import type {
  AttachmentParser,
  ParsedDocument,
  ParseAttachmentInput,
} from "./contracts.js";

export class AliyunOcrParser implements AttachmentParser {
  constructor(private readonly endpoint?: string) {}

  async parse(_input: ParseAttachmentInput): Promise<ParsedDocument> {
    if (!this.endpoint) {
      throw new Error("Aliyun OCR is not configured");
    }
    throw new Error("Aliyun OCR adapter requires production credentials");
  }
}
