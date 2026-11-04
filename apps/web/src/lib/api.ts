import type {
  CreateExperiment,
  Experiment,
  ExperimentEvent,
  Session,
  Summary,
} from "./types";

const API = "/api/v1";

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
