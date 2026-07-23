import { describe, expect, it } from "vitest";
import { crossValidate, field } from "./contracts.js";

describe("crossValidate", () => {
  it("routes conflicting OCR and model dates to review", () => {
    const result = crossValidate(
      field("effectiveDate", "2022-09-07", 0.98, "OCR"),
      field("effectiveDate", "2032-09-07", 0.92, "MODEL"),
    );

    expect(result.status).toBe("REVIEW_REQUIRED");
    expect(result.errorCode).toBe("EVIDENCE_CONFLICT");
  });

  it("accepts agreeing values and keeps the lower confidence", () => {
    const result = crossValidate(
      field("expiryDate", "2032-09-06", 0.98, "OCR"),
      field("expiryDate", "2032-09-06", 0.93, "MODEL"),
    );

    expect(result).toMatchObject({
      status: "CONFIRMED",
      value: "2032-09-06",
      confidence: 0.93,
    });
  });
});
