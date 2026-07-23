import { describe, expect, it, vi } from "vitest";
import { processInspection } from "./process-inspection.js";

describe("processInspection", () => {
  it("stores evidence and routes low confidence to review", async () => {
    const parser = {
      parse: vi.fn().mockResolvedValue({
        pages: 1,
        rawText: "授权期限至2026年12月31日止",
        fields: [
          {
            name: "effectiveDate",
            value: null,
            confidence: 0.61,
            method: "OCR",
          },
        ],
      }),
    };
    const repository = {
      saveFindings: vi.fn().mockResolvedValue(undefined),
      transition: vi.fn().mockResolvedValue(undefined),
    };

    await processInspection(
      {
        taskId: "task-1",
        attachmentId: "attachment-1",
        mime: "image/png",
        bytes: new Uint8Array([1, 2, 3]),
      },
      { parser, repository },
    );

    expect(repository.saveFindings).toHaveBeenCalledOnce();
    expect(repository.transition).toHaveBeenCalledWith(
      "task-1",
      "REVIEW_REQUIRED",
    );
  });

  it("rebuilds attachment fields and stores field-by-field reconciliation", async () => {
    const parser = {
      parse: vi.fn().mockResolvedValue({
        pages: 1,
        rawText: "授权区域仅限浙江省",
        fields: [
          {
            name: "region",
            value: "浙江省",
            confidence: 0.96,
            method: "OCR",
            page: 1,
            evidenceText: "授权区域仅限浙江省",
          },
        ],
      }),
    };
    const repository = {
      saveFindings: vi.fn().mockResolvedValue(undefined),
      saveReconciliation: vi.fn().mockResolvedValue(undefined),
      transition: vi.fn().mockResolvedValue(undefined),
    };

    await processInspection(
      {
        taskId: "task-2",
        attachmentId: "attachment-2",
        attachmentUrl: "https://example.test/auth.pdf",
        mime: "application/pdf",
        bytes: new Uint8Array([1]),
        sourceFields: {
          authorizationCode: null,
          authorizationType: [],
          authorizationLevel: null,
          grantor: null,
          grantees: [],
          brands: [],
          categories: [],
          region: "全国",
          effectiveDate: null,
          expiryDate: null,
          isProjectAuthorization: null,
          projectName: null,
          transferAllowed: null,
        },
      },
      { parser, repository },
    );

    expect(repository.saveReconciliation).toHaveBeenCalledWith(
      "task-2",
      expect.objectContaining({
        fieldComparisons: expect.arrayContaining([
          expect.objectContaining({
            field: "region",
            sourceValue: "全国",
            attachmentValue: "浙江省",
            comparisonStatus: "SOURCE_FIELD_ERROR",
            evidencePage: 1,
          }),
        ]),
      }),
    );
    expect(parser.parse).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceUrl: "https://example.test/auth.pdf",
      }),
    );
  });
});
