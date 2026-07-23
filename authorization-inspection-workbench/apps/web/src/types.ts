export type Risk = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface InspectionTask {
  id: string;
  brand: string;
  code: string;
  name: string;
  status: string;
  risk: Risk;
  issueCount: number;
  assignee: string;
  updatedAt: string;
}
