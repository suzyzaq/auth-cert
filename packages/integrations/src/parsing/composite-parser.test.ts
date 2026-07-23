import { describe, expect, it } from "vitest";
import { CompositeAttachmentParser } from "./composite-parser.js";

const input = {
  attachmentId: "file-1",
  mime: "application/pdf",
  bytes: new Uint8Array([1]),
};

describe("CompositeAttachmentParser", () => {
  it("confirms equal values and preserves both evidence sources", async () => {
    const parser = new CompositeAttachmentParser(
      {
        parse: async () => ({
          pages: 2,
          rawText: "授权区域：浙江省",
          fields: [
            {
              name: "region",
              value: "浙江省",
              confidence: 0.96,
              method: "OCR",
              page: 2,
              evidenceText: "授权区域：浙江省",
            },
          ],
        }),
      },
      {
        parse: async () => ({
          pages: 2,
          rawText: "授权区域：浙江省",
          fields: [
            {
              name: "region",
              value: "浙江省",
              confidence: 0.92,
              method: "MODEL",
              page: 2,
              evidenceText: "授权区域：浙江省",
            },
          ],
        }),
      },
    );

    const result = await parser.parse(input);

    expect(result.fields[0]).toMatchObject({
      name: "region",
      value: "浙江省",
      confidence: 0.92,
      validationStatus: "CONFIRMED",
    });
    expect(result.fields[0]?.evidence).toHaveLength(2);
  });

  it("requires review when OCR and model values conflict", async () => {
    const parser = new CompositeAttachmentParser(
      {
        parse: async () => ({
          pages: 1,
          rawText: "全国",
          fields: [
            { name: "region", value: "全国", confidence: 0.9, method: "OCR" },
          ],
        }),
      },
      {
        parse: async () => ({
          pages: 1,
          rawText: "浙江省",
          fields: [
            { name: "region", value: "浙江省", confidence: 0.9, method: "MODEL" },
          ],
        }),
      },
    );

    const result = await parser.parse(input);

    expect(result.fields[0]).toMatchObject({
      name: "region",
      value: null,
      validationStatus: "CONFLICT",
      errorCode: "EVIDENCE_CONFLICT",
    });
  });
});
