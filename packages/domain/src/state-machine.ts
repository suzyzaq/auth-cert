import type { TaskAction, TaskStatus } from "./inspection.js";

const transitions: Partial<
  Record<TaskStatus, Partial<Record<TaskAction, TaskStatus>>>
> = {
  QUEUED: { START_PARSE: "PARSING" },
  PARSING: {
    PARSE_SUCCESS: "INSPECTED",
    PARSE_FAILURE: "PARSE_FAILED",
  },
  PARSE_FAILED: { START_PARSE: "PARSING", REQUEST_REVIEW: "REVIEW_REQUIRED" },
  INSPECTED: { REQUEST_REVIEW: "REVIEW_REQUIRED" },
  REVIEW_REQUIRED: {
    COMPLETE_REVIEW: "REVIEWED",
    REJECT: "REJECTED",
  },
  REVIEWED: {
    APPROVE: "AWAITING_WRITEBACK",
    REJECT: "REJECTED",
  },
  AWAITING_WRITEBACK: { START_WRITEBACK: "WRITING_BACK" },
  WRITING_BACK: {
    WRITEBACK_SUCCESS: "WRITTEN_BACK",
    WRITEBACK_FAILURE: "REVIEW_REQUIRED",
  },
};

export function transitionTask(
  current: TaskStatus,
  action: TaskAction,
): TaskStatus {
  if (current === "INSPECTED" && action === "APPROVE") {
    throw new Error("review required before approval");
  }

  const next = transitions[current]?.[action];
  if (!next) {
    throw new Error(`transition not allowed: ${current} -> ${action}`);
  }

  return next;
}
