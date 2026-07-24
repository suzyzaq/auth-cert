import { describe, expect, it } from "vitest";
import {
  compareDates,
  rebuildStartDate,
} from "../../packages/domain/src/rules/dates.js";

describe("confirmed production regressions", () => {
  it.each([
    ["BABYCARE", "2032-09-07", "2022-09-06", "2022-09-07", "2032-09-06"],
    ["印芭贝", "2030-05-06", "2020-05-07", "2020-05-07", "2030-05-06"],
    ["恒净森", "2029-12-14", "2029-12-13", "2019-12-14", "2029-12-13"],
  ])(
    "detects confirmed date mismatch for %s",
    (_, sourceStart, sourceEnd, evidenceStart, evidenceEnd) => {
      expect(
        compareDates(sourceStart, sourceEnd, evidenceStart, evidenceEnd),
      ).toMatchObject({ risk: "CRITICAL" });
    },
  );

  it("keeps HOYO start date empty when the evidence only contains an end date", () => {
    expect(rebuildStartDate("授权期限至2026年12月31日止")).toBeNull();
  });
});

