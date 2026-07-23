import { describe, expect, it } from "vitest";
import { filterRules, inspectionRules } from "./rule-catalog.js";

describe("rule catalog", () => {
  it("combines category, severity and keyword filters", () => {
    expect(
      filterRules(inspectionRules, {
        category: "FIELD",
        severity: "CRITICAL",
        query: "日期",
      }).map((rule) => rule.id),
    ).toEqual(["date-order"]);
  });

  it("contains representative rules for all six inspection categories", () => {
    expect(new Set(inspectionRules.map((rule) => rule.category))).toEqual(
      new Set([
        "AVAILABILITY",
        "FRESHNESS",
        "CONSISTENCY",
        "FIELD",
        "BUSINESS",
        "EVIDENCE",
      ]),
    );
  });

  it("covers attachment-first reconciliation states and correction gates", () => {
    const joined = inspectionRules
      .flatMap((rule) => [
        rule.name,
        rule.description,
        rule.condition,
        ...rule.fields,
      ])
      .join(" ");

    expect(joined).toContain("附件事实优先");
    expect(joined).toContain("ATTACHMENT_FIELD_MISSING");
    expect(joined).toContain("CHAIN_INCOMPLETE");
    expect(joined).toContain("品牌不低于 0.90");
    expect(joined).toContain("AUTHORIZATION_CODE_MISMATCH");
  });
});
