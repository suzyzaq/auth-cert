import { describe, expect, it } from "vitest";
import { compareDates, rebuildStartDate } from "./dates.js";
import { reviewAuthorizationChain } from "./authorization-chain.js";

describe("confirmed field regressions", () => {
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

  it("does not invent a HOYO start date", () => {
    expect(rebuildStartDate("授权期限至2026年12月31日止")).toBeNull();
  });

  it("marks delimiter counts as review evidence instead of rewriting level", () => {
    expect(
      reviewAuthorizationChain({
        level: "1级",
        grant: "公司A-公司A",
        authed: "公司B-公司B",
      }),
    ).toMatchObject({
      errorCode: "AUTHORIZATION_CHAIN_REVIEW_REQUIRED",
      proposedLevel: null,
    });
  });
});
