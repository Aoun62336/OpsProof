import type {
  CreateExperiment,
  Experiment,
  ExperimentEvent,
  Incident,
  IncidentEvent,
  IncidentStatus,
  Session,
  Summary,
} from "./types";

const API = "/api/v1";

export interface KubernetesObservation {
  name: string;
  observed_at: string;
  resource: {
    metadata: { name: string; namespace: string; uid: string; resourceVersion: string };
    spec: { replicas: number; template: { spec: { containers: { image: string; resources: { requests: { cpu: string; memory: string }; limits: { cpu: string; memory: string } } }[] } } };
    status: { readyReplicas?: number; availableReplicas?: number };
  };
  telemetry: { ready: boolean; queued: number; sample_time: number };
}
export interface KubernetesRecovery {
  id: string; status: string; target_image: string; target_uid: string;
  expires_at: string; created_at: string; error: string | null;
}
export const getKubernetesWorkloads = () => request<{ enabled: boolean; observations: KubernetesObservation[] }>("/kubernetes/workloads");
export const getKubernetesRecoveries = () => request<KubernetesRecovery[]>("/kubernetes/recoveries");
export const proposeKubernetesRecovery = (incident: string, run: string) => request<KubernetesRecovery>("/kubernetes/recoveries", {
  method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() },
  body: JSON.stringify({ action: "restore_demo_worker", incident_fingerprint: incident, run_id: run }),
});
export const approveKubernetesRecovery = (id: string) => request<KubernetesRecovery>(`/kubernetes/recoveries/${encodeURIComponent(id)}/approve`, {
  method: "POST", body: JSON.stringify({ confirmation: "APPROVE DEMO WORKER RESTORE" }),
});

let csrfToken: string | null = null;

export class ApiError extends Error {
  readonly status: number;
  constructor(
    status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readResponse<T>(
  response: Response,
): Promise<T> {
  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`;

    throw new ApiError(response.status, detail);
  }

  return body as T;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();

  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (!["GET", "HEAD"].includes(method) && csrfToken) {
    headers.set("X-OpsProof-CSRF", csrfToken);
  }

  const response = await fetch(`${API}${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  return readResponse<T>(response);
}

export async function getSession(): Promise<Session | null> {
  const response = await fetch(`${API}/auth/session`, {
    credentials: "same-origin",
    cache: "no-store",
  });

  if (response.status === 401) {
    csrfToken = null;
    return null;
  }

  const session = await readResponse<Session>(response);
  csrfToken = session.csrf_token;

  return session;
}

export async function login(
  accessKey: string,
): Promise<Session> {
  const response = await fetch(`${API}/auth/login`, {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      access_key: accessKey,
    }),
  });

  const session = await readResponse<Session>(response);
  csrfToken = session.csrf_token;

  return session;
}

export async function logout(): Promise<void> {
  await request("/auth/logout", {
    method: "POST",
  });

  csrfToken = null;
}

export function getSummary(): Promise<Summary> {
  return request<Summary>("/summary");
}

export function getExperiments(
  limit = 50,
  offset = 0,
): Promise<Experiment[]> {
  return request<Experiment[]>(
    `/experiments?limit=${limit}&offset=${offset}`,
  );
}

export function getExperiment(
  id: string,
): Promise<Experiment> {
  return request<Experiment>(
    `/experiments/${encodeURIComponent(id)}`,
  );
}

export function getExperimentEvents(
  id: string,
): Promise<ExperimentEvent[]> {
  return request<ExperimentEvent[]>(
    `/experiments/${encodeURIComponent(id)}/events`,
  );
}

export function createExperiment(
  payload: CreateExperiment,
  idempotencyKey: string,
): Promise<Experiment> {
  return request<Experiment>("/experiments", {
    method: "POST",
    headers: {
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
  });
}

export function getIncidents(
  status?: IncidentStatus,
): Promise<Incident[]> {
  const query = status
    ? `?status=${status}&limit=50`
    : "?limit=50";

  return request<Incident[]>(
    `/incidents${query}`,
  );
}

export function getIncidentEvents(
  fingerprint: string,
): Promise<IncidentEvent[]> {
  return request<IncidentEvent[]>(
    `/incidents/${encodeURIComponent(fingerprint)}/events`,
  );
}

export function getCapabilities(): Promise<
  import("./types").OperationalCapabilities
> {
  return request("/capabilities");
}

export function listInvestigations(
  fingerprint: string,
): Promise<import("./types").Investigation[]> {
  return request(
    `/investigations?incident_fingerprint=${encodeURIComponent(fingerprint)}`,
  );
}

export function requestInvestigation(
  fingerprint: string,
  runId: string | null,
  key: string,
): Promise<import("./types").Investigation> {
  return request("/investigations", {
    method: "POST",
    headers: {
      "Idempotency-Key": key,
    },
    body: JSON.stringify({
      incident_fingerprint: fingerprint,
      run_id: runId,
    }),
  });
}

export function requestAiEvaluation(
  id: string,
): Promise<import("./types").Investigation> {
  return request(
    `/investigations/${encodeURIComponent(id)}/ai`,
    {
      method: "POST",
    },
  );
}

export function listRecoveries(): Promise<
  import("./types").Recovery[]
> {
  return request("/recoveries");
}

export function proposeRecovery(
  investigationId: string,
  key: string,
): Promise<import("./types").Recovery> {
  return request("/recoveries", {
    method: "POST",
    headers: {
      "Idempotency-Key": key,
    },
    body: JSON.stringify({
      investigation_id: investigationId,
    }),
  });
}

export function approveRecovery(
  id: string,
): Promise<import("./types").Recovery> {
  return request(
    `/recoveries/${encodeURIComponent(id)}/approve`,
    {
      method: "POST",
      body: JSON.stringify({
        confirmation: "APPROVE DEMO WORKER RESUME",
      }),
    },
  );
}

export function rejectRecovery(
  id: string,
): Promise<import("./types").Recovery> {
  return request(
    `/recoveries/${encodeURIComponent(id)}/reject`,
    {
      method: "POST",
    },
  );
}

export function getRecoveryEvents(
  id: string,
): Promise<
  {
    id: number;
    type: string;
    details: Record<string, unknown>;
    created_at: string;
  }[]
> {
  return request(
    `/recoveries/${encodeURIComponent(id)}/events`,
  );
}

// M6 ledger is an opt-in, read-only console surface. Mutations are not exposed here.
export interface M6Trial {
  id: string;
  scenario: string;
  target: string;
  phase: string;
  source_revision: string;
  approved_test_scope: boolean;
  injection_acknowledged: boolean;
  independent_verified: boolean;
  cleanup_verified: boolean;
  abort_requested: boolean;
  created_at: string;
  updated_at: string;
  error: string | null;
  dispatch_intent_at?: string | null;
  target_uid?: string | null;
}
export interface M6TrialEvent {
  id: number;
  kind: string;
  details: Record<string, unknown>;
  created_at: string;
}
export const getM6Trials = () => request<M6Trial[]>("/m6/trials");
export const getM6TrialEvents = (id: string) =>
  request<M6TrialEvent[]>(`/m6/trials/${encodeURIComponent(id)}/events`);
export interface M6TrialArtifact {
  id: number;
  kind: string;
  relative_path: string;
  sha256: string;
  created_at: string;
  observations?: Record<string, unknown>;
}
export const getM6TrialArtifacts = (id: string) =>
  request<M6TrialArtifact[]>(`/m6/trials/${encodeURIComponent(id)}/artifacts`);

export interface M6Verification {
  observer_id: string;
  dispatch_id: string;
  target_uid: string;
  verified_at: string;
  cleanup_verified: boolean;
  hypothesis_verified: boolean;
  report_sha256: string;
  observer_sha256: string;
  checks: Record<string, boolean>;
}
export const getM6Verifications = (id: string) =>
  request<M6Verification[]>(`/m6/trials/${encodeURIComponent(id)}/verifications`);
