export interface InspectionTaskRow {
  id: string;
  sourceRecordId: string;
  sourceVersion: string;
  brand: string;
  status: string;
  sourcePayload: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}

export interface NewInspectionTask {
  sourceRecordId: string;
  sourceVersion: string;
  brand: string;
  sourcePayload: Record<string, unknown>;
}
