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
