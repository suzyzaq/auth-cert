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
});
