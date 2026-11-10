// Local-only, finite constant-arrival-rate workload. This does NOT run chaos,
// Kubernetes actions, recovery, or external network requests.
import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';

const base = __ENV.M6_BASE_URL || 'http://127.0.0.1:18088';
const runId = __ENV.M6_RUN_ID || '';
const rate = Number(__ENV.M6_RATE || 1);
const seconds = Number(__ENV.M6_SECONDS || 30);
const durationMs = Number(__ENV.M6_DURATION_MS || 250);
const vus = Number(__ENV.M6_VUS || 4);

if (!['http://127.0.0.1:18088', 'http://localhost:18088'].includes(base)) {
  throw new Error('Refusing to load-test any URL except the M5 Kubernetes port-forward');
}
if (!/^[a-z0-9-]{8,40}$/.test(runId)) {
  throw new Error('Set M6_RUN_ID to a fresh lowercase identifier (8-40 chars)');
}
if (![rate, seconds, durationMs, vus].every(Number.isInteger) ||
    rate < 1 || rate > 5 || seconds < 10 || seconds > 120 ||
    rate * seconds > 120 || durationMs < 50 || durationMs > 2000 ||
    vus < 1 || vus > 16) {
  throw new Error('Bounded workload limits exceeded');
}

export const options = {
  discardResponseBodies: false,
  scenarios: {
    bounded_jobs: {
      executor: 'constant-arrival-rate',
      rate, timeUnit: '1s', duration: `${seconds}s`,
      preAllocatedVUs: vus, maxVUs: Math.min(16, vus * 2),
      gracefulStop: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    dropped_iterations: ['count==0'],
    checks: ['rate==1'],
  },
};

export default function () {
  const key = `m6-${runId}-${exec.vu.idInTest}-${exec.vu.iterationInScenario}`;
  const result = http.post(`${base}/api/v1/jobs`,
    JSON.stringify({ duration_ms: durationMs }), {
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      timeout: '5s',
      tags: { operation: 'create_job' },
    });
  let id = null;
  if (result.status === 202) {
    try { id = result.json('id'); } catch (_) { id = null; }
  }
  const accepted = result.status === 202 &&
    typeof id === 'string' && /^[a-f\d-]{36}$/i.test(id);
  check(result, { 'durable job accepted': () => accepted });
  // Retain receipts even for unsuccessful calls; never log credentials.
  console.log(JSON.stringify({
    kind: 'm6_job_receipt', run_id: runId, key, id,
    accepted, status: result.status,
  }));
}

export function handleSummary(data) {
  const path = __ENV.M6_SUMMARY_PATH || '.runtime/m6/k6-summary.json';
  if (path.startsWith('/') || path.includes('..')) {
    throw new Error('Summary path must be relative and non-traversing');
  }
  return { [path]: JSON.stringify(data, null, 2) + '\n' };
}
