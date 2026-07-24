import type { RiskLevel } from "../inspection.js";

const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

export interface DateComparison {
  matches: boolean;
  risk: RiskLevel;
  errors: Array<"EFFECTIVE_DATE_MISMATCH" | "EXPIRY_DATE_MISMATCH">;
}

export function compareDates(
  sourceStart: string,
  sourceEnd: string,
  evidenceStart: string,
  evidenceEnd: string,
): DateComparison {
  for (const value of [sourceStart, sourceEnd, evidenceStart, evidenceEnd]) {
    if (!isoDatePattern.test(value)) throw new Error(`invalid ISO date: ${value}`);
  }

  const errors: DateComparison["errors"] = [];
  if (sourceStart !== evidenceStart) errors.push("EFFECTIVE_DATE_MISMATCH");
  if (sourceEnd !== evidenceEnd) errors.push("EXPIRY_DATE_MISMATCH");

  return {
    matches: errors.length === 0,
    risk: errors.length > 0 ? "CRITICAL" : "LOW",
    errors,
  };
}

export function rebuildStartDate(text: string): string | null {
  const explicit = text.match(
    /(?:自|开始日期[:：]?)\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:起|开始|生效)?/,
  );
  if (!explicit) return null;
  const [, year, month, day] = explicit;
  return `${year}-${month?.padStart(2, "0")}-${day?.padStart(2, "0")}`;
}
