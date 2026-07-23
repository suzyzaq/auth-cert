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
});
