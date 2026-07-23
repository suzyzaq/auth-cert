export type UserRole = "INSPECTOR" | "REVIEWER" | "ADMIN";
export type Permission =
  | "READ_TASK"
  | "REVIEW_TASK"
  | "MANAGE_RULE"
  | "APPROVE_WRITEBACK";

const permissions: Record<UserRole, ReadonlySet<Permission>> = {
  INSPECTOR: new Set(["READ_TASK"]),
  REVIEWER: new Set(["READ_TASK", "REVIEW_TASK"]),
  ADMIN: new Set([
    "READ_TASK",
    "REVIEW_TASK",
    "MANAGE_RULE",
    "APPROVE_WRITEBACK",
  ]),
};

export function authorize(role: UserRole, permission: Permission): true {
  if (!permissions[role].has(permission)) {
    throw new Error(`forbidden: ${role} lacks ${permission}`);
  }
  return true;
}
