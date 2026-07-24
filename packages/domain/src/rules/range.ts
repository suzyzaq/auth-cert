export interface RangeFinding {
  errorCode:
    | "FULL_CATEGORY_OVERCLAIM"
    | "NATIONWIDE_OVERCLAIM"
    | "PROJECT_MISMATCH";
  field: "category" | "region" | "project";
}

export function compareAuthorizationRange(input: {
  sourceCategory: string;
  sourceRegion: string;
  sourceProject: string | null;
  evidenceCategory: string | null;
  evidenceRegion: string | null;
  evidenceProject: string | null;
}): RangeFinding[] {
  const findings: RangeFinding[] = [];
  if (
    input.sourceCategory === "全品类" &&
    input.evidenceCategory &&
    input.evidenceCategory !== "全品类"
  ) {
    findings.push({
      field: "category",
      errorCode: "FULL_CATEGORY_OVERCLAIM",
    });
  }
  if (
    input.sourceRegion === "全国" &&
    input.evidenceRegion &&
    input.evidenceRegion !== "全国"
  ) {
    findings.push({ field: "region", errorCode: "NATIONWIDE_OVERCLAIM" });
  }
  if (
    input.evidenceProject &&
    input.sourceProject !== input.evidenceProject
  ) {
    findings.push({ field: "project", errorCode: "PROJECT_MISMATCH" });
  }
  return findings;
}
