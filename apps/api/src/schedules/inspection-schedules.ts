import { createHash } from "node:crypto";

export const inspectionSchedule = {
  incremental: "30 17 * * 1-5",
  full: "0 2 * * 0",
} as const;

export type InspectionScheduleKind = keyof typeof inspectionSchedule;

export function scheduledBatchKey(
  kind: InspectionScheduleKind,
  scheduledAt: Date,
): string {
  const window = scheduledAt.toISOString().slice(0, 16);
  const digest = createHash("sha256")
    .update(`${kind}:${window}`)
    .digest("hex")
    .slice(0, 16);
  return `scheduled:${kind}:${digest}`;
}

