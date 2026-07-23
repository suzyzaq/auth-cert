import { describe, expect, it } from "vitest";
import {
  reconcileAuthorization,
  type AttachmentAuthorizationFields,
  type SourceAuthorizationFields,
} from "./reconciliation.js";

const source: SourceAuthorizationFields = {
  authorizationCode: "AUTH-001",
  authorizationType: ["普通授权"],
  authorizationLevel: 2,
  grantor: "甲公司",
  grantees: ["乙公司"],
  brands: ["Canon"],
  categories: ["全品类"],
  region: "全国",
  effectiveDate: "2026-01-02",
  expiryDate: "2026-12-31",
  isProjectAuthorization: false,
  projectName: null,
  transferAllowed: null,
};

function attachment(
  values: Partial<AttachmentAuthorizationFields> = {},
): AttachmentAuthorizationFields {
  return {
    authorizationCode: "AUTH-001",
    authorizationType: ["项目授权"],
    authorizationLevel: null,
    grantor: "甲公司",
    grantees: ["乙公司"],
    brandRaw: ["佳能/Canon"],
    brandStandard: ["Canon"],
    categoryRaw: ["打印机"],
    categoryStandard: ["打印机"],
    regionRaw: "浙江省",
    regionStandard: "浙江省",
    effectiveDate: "2026年1月2日",
    expiryDate: "2026-12-31",
    isProjectAuthorization: true,
    projectName: "办公设备采购项目",
    transferAllowed: null,
    ...values,
  };
}

const evidence = [
  {
    attachmentId: "file-1",
    attachmentUrl: "https://example.test/auth.pdf",
    field: "region",
    page: 2,
    text: "授权区域仅限浙江省",
    extractionMethod: "OCR" as const,
    confidence: 0.97,
  },
];

describe("reconcileAuthorization", () => {
  it("normalizes explicit dates and reports source errors with evidence", () => {
    const result = reconcileAuthorization({
      recordId: "record-1",
      attachmentUrl: "https://example.test/auth.pdf",
      source,
      attachment: attachment({ effectiveDate: "2025年1月2日" }),
      evidence: [
        ...evidence,
        {
          ...evidence[0]!,
          field: "effectiveDate",
          page: 1,
          text: "授权期限自2025年1月2日起",
        },
      ],
    });

    const date = result.fieldComparisons.find(
      (item) => item.field === "effectiveDate",
    );
    expect(date).toMatchObject({
      attachmentValue: "2025-01-02",
      comparisonStatus: "SOURCE_FIELD_ERROR",
      correctionAction: "update",
      evidencePage: 1,
    });
  });

  it("does not infer authorization level from transfer authorization", () => {
    const result = reconcileAuthorization({
      recordId: "record-1",
      attachmentUrl: "https://example.test/auth.pdf",
      source,
      attachment: attachment({
        authorizationType: ["转授权"],
        authorizationLevel: null,
      }),
      evidence,
    });

    const level = result.fieldComparisons.find(
      (item) => item.field === "authorizationLevel",
    );
    expect(level?.comparisonStatus).toBe("CHAIN_INCOMPLETE");
    expect(level?.correctedValue).toBeNull();
    expect(result.manualReviewReasons).toContain("授权链不完整，无法确定授权层级");
  });

  it("marks a field unverified when the attachment does not state it", () => {
    const result = reconcileAuthorization({
      recordId: "record-1",
      attachmentUrl: "https://example.test/auth.pdf",
      source,
      attachment: attachment({ regionRaw: null, regionStandard: null }),
      evidence: [],
    });

    const region = result.fieldComparisons.find(
      (item) => item.field === "region",
    );
    expect(region).toMatchObject({
      attachmentValue: null,
      comparisonStatus: "ATTACHMENT_FIELD_MISSING",
      correctionAction: "review",
    });
  });

  it("prevents automatic correction when project scope is understated", () => {
    const result = reconcileAuthorization({
      recordId: "record-1",
      attachmentUrl: "https://example.test/auth.pdf",
      source,
      attachment: attachment(),
      evidence,
    });

    expect(result.canAutoCorrect).toBe(false);
    expect(result.dataIssues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          issueCode: "PROJECT_AUTHORIZATION_MISSING",
          severity: "high",
        }),
        expect.objectContaining({
          issueCode: "CATEGORY_SCOPE_OVERSTATED",
        }),
      ]),
    );
  });
});
