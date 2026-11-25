export type RunStatus =
  | "queued"
  | "running"
  | "verifying"
  | "succeeded"
  | "failed";

export interface Experiment {
  id: string;
  scenario: string;
  count: number;
  duration_ms: number;
  status: RunStatus;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExperimentEvent {
  id: number;
  type: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Summary {
  total: number;
  counts: Record<RunStatus, number>;
  recent: Experiment[];
  generated_at: string;
}

export interface Session {
  authenticated: true;
  csrf_token: string;
}

export interface CreateExperiment {
  scenario: "queue-burst";
  count: number;
  duration_ms: number;
}

export type IncidentStatus =
  | "firing"
  | "resolved";

export interface Incident {
  fingerprint: string;
  name: string;
  target: string;
  severity: string;
  summary: string;
  status: IncidentStatus;
  started_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface IncidentEvent {
  id: number;
  status: IncidentStatus;
  created_at: string;
}

export interface Investigation {
  id: string;
  incident_fingerprint: string;
  run_id: string | null;
  status: "queued" | "running" | "ready" | "failed";
  snapshot: Record<string, unknown>;
  baseline: Record<string, unknown>;

  ai_status:
    | "not_requested"
    | "queued"
    | "running"
    | "ready"
    | "failed";

  ai_result: Record<string, unknown> | null;
  ai_provider: string | null;
  ai_model: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Recovery {
  id: string;
  investigation_id: string;
  incident_fingerprint: string;
  run_id: string;
  action: "resume_demo_worker";

  status:
    | "pending_approval"
    | "approved"
    | "running"
    | "verifying"
    | "succeeded"
    | "failed"
    | "rejected"
    | "expired"
    | "indeterminate";

  attempts: number;
  created_at: string;
  expires_at: string;
  approved_at: string | null;
  started_at: string | null;
  verify_by: string | null;
  completed_at: string | null;
  result: Record<string, unknown>;
  error: string | null;
}

export type ExecutionEnvironment = "local" | "temporary-eks";

export interface OperationalCapabilities {
  environment?: ExecutionEnvironment;
  environment_label?: string;
  kubernetes_observation_enabled?: boolean;
  kubernetes_recovery_enabled?: boolean;
  recovery_enabled: boolean;
  ai_enabled: boolean;
  ai_provider: string;
}
