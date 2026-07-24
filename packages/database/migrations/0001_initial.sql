CREATE TABLE IF NOT EXISTS inspection_tasks (
  id UUID PRIMARY KEY,
  source_record_id TEXT NOT NULL,
  source_version TEXT NOT NULL,
  brand TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED',
  source_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source_record_id, source_version)
);

CREATE TABLE IF NOT EXISTS inspection_findings (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES inspection_tasks(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  source_value JSONB,
  proposed_value JSONB,
  confidence NUMERIC(5,4) NOT NULL,
  risk TEXT NOT NULL,
  error_code TEXT NOT NULL,
  evidence JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS inspection_tasks_status_idx
  ON inspection_tasks(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS inspection_tasks_brand_idx
  ON inspection_tasks(brand);
CREATE INDEX IF NOT EXISTS inspection_findings_task_idx
  ON inspection_findings(task_id, risk);
