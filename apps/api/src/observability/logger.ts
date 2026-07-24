import { sanitizeLog } from "../operations/sanitize-log.js";

export interface StructuredLog {
  level: "info" | "warn" | "error";
  event: string;
  traceId?: string;
  data?: Record<string, unknown>;
}

export function createLogEntry(entry: StructuredLog): Record<string, unknown> {
  return sanitizeLog({
    timestamp: new Date().toISOString(),
    ...entry,
  }) as Record<string, unknown>;
}

