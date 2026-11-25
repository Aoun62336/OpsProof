import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Boxes,
  CheckCircle2,
  Clock3,
  Cpu,
  GitBranch,
  Layers,
  MemoryStick,
  ShieldCheck,
} from "lucide-react";
import {
  approveKubernetesRecovery,
  getKubernetesRecoveries,
  getKubernetesWorkloads,
  proposeKubernetesRecovery,
  type KubernetesObservation,
  type KubernetesRecovery,
} from "../lib/api";
import { formatDate, titleCase } from "../lib/format";
import { requestShare, timestampIsFresh } from "../lib/kubernetes";

type View = "Workloads" | "Deployments" | "Capacity" | "Runbooks";
type Tone =
  | "neutral"
  | "success"
  | "warning"
  | "failed"
  | "running"
  | "verifying";

function Status({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return <span className={`kube-status kube-status--${tone}`}>{children}</span>;
}

function Metric({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: ReactNode;
  note: string;
  icon: ReactNode;
}) {
  return (
    <div className="panel kube-metric">
      <p className="kube-metric__label">
        {icon}
        {label}
      </p>
      <p className="kube-metric__value">{value}</p>
      <p className="kube-caption">{note}</p>
    </div>
  );
}

function ResourceMeter({
  label,
  request,
  limit,
  icon,
}: {
  label: string;
  request: string | undefined;
  limit: string | undefined;
  icon: ReactNode;
}) {
  const share = requestShare(request, limit);
  return (
    <div className="kube-resource">
      <h3>
        {icon}
        {label} request
      </h3>
      <p className="kube-resource__value">
        {request ?? "Unavailable"}
        <span> / {limit ?? "unavailable"} limit</span>
      </p>
      {share !== null && (
        <progress
          value={Math.min(share, 100)}
          max={100}
          aria-label={`Configured ${label} request relative to limit`}
          aria-valuetext={`${request} requested of ${limit} limit`}
        />
      )}
      <div className="kube-resource__scale">
        <span>
          {share === null ? "Ratio unavailable" : "Configured request"}
        </span>
        <span>{limit ?? "Unavailable"} limit</span>
      </div>
    </div>
  );
}

function WorkloadCard({
  observation,
  view,
  now,
  unavailable,
  cloud = false,
}: {
  observation: KubernetesObservation;
  view: View;
  now: number;
  unavailable: boolean;
  cloud?: boolean;
}) {
  const resource = observation.resource;
  const container = resource.spec.template.spec.containers[0];
  const fresh =
    !unavailable &&
    timestampIsFresh(Date.parse(observation.observed_at), now, 15_000);
  const sampleTime = observation.telemetry?.sample_time * 1000;
  const metricsFresh = fresh && timestampIsFresh(sampleTime, now, 30_000);
  const ready = resource.status.readyReplicas ?? 0;
  const desired = resource.spec.replicas;
  const available = fresh && ready >= desired && desired > 0;
  const dependencies = metricsFresh
    ? observation.telemetry.ready
      ? "Ready"
      : "Not ready"
    : "Unknown";
  const queued = observation.telemetry?.queued;
  const queueValue =
    Number.isFinite(queued) && queued >= 0 ? queued : "Unknown";
  const requests = container?.resources?.requests;
  const limits = container?.resources?.limits;
  const health = fresh ? (available ? "Ready" : "Not ready") : "Health unknown";
  const healthTone = available ? "success" : "warning";

  return (
    <article
      className="kube-workload"
      aria-label={`${resource.metadata.name} observations`}
    >
      <div className="kube-observed">
        <Status tone={fresh ? "neutral" : "warning"}>
          <Clock3 size={14} aria-hidden="true" />
          {fresh ? "Recent observation" : "Current state unknown"}
        </Status>
        <time dateTime={observation.observed_at}>
          {formatDate(observation.observed_at)}
        </time>
      </div>
      {!fresh && (
        <p className="kube-notice" role="status">
          Fresh observation unavailable. Values below describe the last recorded
          state.
        </p>
      )}
      {view !== "Deployments" && view !== "Runbooks" && (
        <div className="kube-metrics">
          <Metric
            label={view === "Capacity" ? "Queued jobs" : "Ready replicas"}
            value={
              view === "Capacity" ? (
                <>
                  {queueValue}
                  <small> jobs</small>
                </>
              ) : (
                <>
                  {ready}
                  <small> / {desired}</small>
                </>
              )
            }
            note={
              view === "Capacity"
                ? metricsFresh
                  ? "At last scrape"
                  : "Fresh queue evidence unavailable"
                : fresh
                  ? "Ready / requested"
                  : "Last observed ready / requested"
            }
            icon={
              view === "Capacity" ? (
                <Layers size={17} aria-hidden="true" />
              ) : (
                <Boxes size={17} aria-hidden="true" />
              )
            }
          />
          <Metric
            label={view === "Capacity" ? "Worker replicas" : "Dependencies"}
            value={
              view === "Capacity" ? (
                <>
                  {ready}
                  <small> / {desired}</small>
                </>
              ) : (
                dependencies
              )
            }
            note={
              view === "Capacity"
                ? fresh
                  ? "Ready / requested"
                  : "Last observed ready / requested"
                : "Aggregate service check"
            }
            icon={
              view === "Capacity" ? (
                <Boxes size={17} aria-hidden="true" />
              ) : (
                <CheckCircle2 size={17} aria-hidden="true" />
              )
            }
          />
          <Metric
            label={view === "Capacity" ? "Dependencies" : "Queued jobs"}
            value={
              view === "Capacity" ? (
                dependencies
              ) : (
                <>
                  {queueValue}
                  <small> jobs</small>
                </>
              )
            }
            note={
              view === "Capacity"
                ? "Aggregate service check"
                : metricsFresh
                  ? "At last scrape"
                  : "Fresh queue evidence unavailable"
            }
            icon={
              view === "Capacity" ? (
                <CheckCircle2 size={17} aria-hidden="true" />
              ) : (
                <Layers size={17} aria-hidden="true" />
              )
            }
          />
        </div>
      )}
      <section className="panel kube-panel">
        <header className="kube-panel__header">
          <div className="kube-identity">
            <span className="kube-icon">
              <Box size={20} aria-hidden="true" />
            </span>
            <div>
              <h2>{resource.metadata.name}</h2>
              <p className="kube-caption mono">{resource.metadata.namespace}</p>
            </div>
          </div>
          {view === "Capacity" ? (
            <Status>Configured resources</Status>
          ) : (
            <Status tone={healthTone}>
              {available ? (
                <CheckCircle2 size={14} aria-hidden="true" />
              ) : (
                <Clock3 size={14} aria-hidden="true" />
              )}
              {health}
            </Status>
          )}
        </header>
        {view === "Deployments" ? (
          <>
            <div className="kube-image">
              <p className="kube-caption">
                <GitBranch size={16} aria-hidden="true" />
                Observed container image
              </p>
              <p className="mono">{container?.image ?? "Unavailable"}</p>
            </div>
            <dl className="kube-details">
              <div>
                <dt>Namespace</dt>
                <dd className="mono">{resource.metadata.namespace}</dd>
              </div>
              <div>
                <dt>Resource version</dt>
                <dd className="mono">{resource.metadata.resourceVersion}</dd>
              </div>
              <div>
                <dt>Requested replicas</dt>
                <dd>{desired}</dd>
              </div>
              <div>
                <dt>Ready replicas{!fresh && " · Last observed"}</dt>
                <dd>{ready}</dd>
              </div>
            </dl>
          </>
        ) : view === "Capacity" ? (
          <>
            <div className="kube-resources">
              <ResourceMeter
                label="CPU"
                request={requests?.cpu}
                limit={limits?.cpu}
                icon={<Cpu size={17} aria-hidden="true" />}
              />
              <ResourceMeter
                label="Memory"
                request={requests?.memory}
                limit={limits?.memory}
                icon={<MemoryStick size={17} aria-hidden="true" />}
              />
            </div>
            <p className="kube-panel__footer">
              Bars show configured requests relative to limits. Measured CPU and
              memory consumption are unavailable in this observation.
            </p>
          </>
        ) : (
          <dl className="kube-details">
            <div>
              <dt>Replica availability{!fresh && " · Last observed"}</dt>
              <dd className="kube-replicas">
                <span
                  className={`kube-replica${available ? " kube-replica--ready" : ""}`}
                >
                  <Boxes size={18} aria-hidden="true" />
                </span>
                {ready} ready of {desired} requested
              </dd>
            </div>
            <div>
              <dt>Service dependencies</dt>
              <dd>{dependencies}</dd>
            </div>
            <div>
              <dt>CPU request / limit</dt>
              <dd className="mono">
                {requests?.cpu ?? "Unavailable"} /{" "}
                {limits?.cpu ?? "Unavailable"}
              </dd>
            </div>
            <div>
              <dt>Memory request / limit</dt>
              <dd className="mono">
                {requests?.memory ?? "Unavailable"} /{" "}
                {limits?.memory ?? "Unavailable"}
              </dd>
            </div>
          </dl>
        )}
        <details className="kube-technical">
          <summary>Workload identity and observation details</summary>
          <dl className="kube-details">
            <div>
              <dt>Workload UID</dt>
              <dd className="mono">{resource.metadata.uid}</dd>
            </div>
            <div>
              <dt>Metrics last scraped</dt>
              <dd>
                {Number.isFinite(sampleTime) && sampleTime > 0
                  ? formatDate(new Date(sampleTime).toString())
                  : "Not recorded"}
              </dd>
            </div>
            <div>
              <dt>Observation freshness</dt>
              <dd>{fresh ? "Within 15 seconds" : "Unavailable"}</dd>
            </div>
            <div>
              <dt>Metric freshness</dt>
              <dd>
                {metricsFresh
                  ? "Within 30 seconds"
                  : "Fresh metrics unavailable"}
              </dd>
            </div>
          </dl>
        </details>
      </section>
      {view === "Capacity" && (
        <p className="kube-caption">
          {cloud ? "Temporary EKS - Measured consumption and cloud cost estimates are unavailable here."
            : "Local sandbox \u00b7 Cloud billing is not configured."}
        </p>
      )}
    </article>
  );
}

const RECOVERY_TONES: Record<string, Tone> = {
  pending_approval: "warning",
  approved: "running",
  running: "running",
  verifying: "verifying",
  succeeded: "success",
  failed: "failed",
  rejected: "failed",
  expired: "neutral",
  indeterminate: "warning",
};

function RecoveryCard({
  recovery,
  now,
  busy,
  approve,
  canApprove,
}: {
  recovery: KubernetesRecovery;
  now: number;
  busy: boolean;
  approve: () => void;
  canApprove: boolean;
}) {
  const expires = Date.parse(recovery.expires_at);
  const approvalValid = Number.isFinite(expires) && expires > now;
  return (
    <article
      className="panel kube-panel"
      aria-label={`Worker restoration ${recovery.id}`}
    >
      <header className="kube-panel__header">
        <div>
          <h3>Worker restoration</h3>
          <p className="kube-caption">
            Proposed {formatDate(recovery.created_at)}
          </p>
        </div>
        <Status tone={RECOVERY_TONES[recovery.status] ?? "neutral"}>
          {titleCase(recovery.status)}
        </Status>
      </header>
      <div className="kube-recovery__body">
        {recovery.status === "succeeded" && (
          <p className="kube-verified">
            <ShieldCheck size={18} aria-hidden="true" />
            Independent verification completed
          </p>
        )}
        {recovery.status === "verifying" && (
          <p>Waiting for independent outcome verification.</p>
        )}
        {recovery.status === "indeterminate" && (
          <p className="kube-notice">
            Outcome is uncertain. Inspect the recorded evidence before any
            further action.
          </p>
        )}
        {recovery.error && (
          <p className="inline-error" role="alert">
            {recovery.error}
          </p>
        )}
        {recovery.status === "pending_approval" && canApprove && (
          <div className="kube-approval">
            <p>
              {approvalValid
                ? `Approval expires in ${Math.ceil((expires - now) / 1000)} seconds`
                : "Approval expired or its expiry is unavailable"}
            </p>
            <button
              className="button button--primary"
              type="button"
              disabled={busy || !approvalValid}
              onClick={approve}
            >
              Approve restoring one demo worker
            </button>
          </div>
        )}
        <dl className="kube-details kube-details--flush">
          <div>
            <dt>Approval expiry</dt>
            <dd>{formatDate(recovery.expires_at)}</dd>
          </div>
          <div>
            <dt>Completed</dt>
            <dd>{formatDate(recovery.completed_at ?? null)}</dd>
          </div>
        </dl>
      </div>
      <details className="kube-technical">
        <summary>Recovery identity and target details</summary>
        <dl className="kube-details">
          <div>
            <dt>Recovery ID</dt>
            <dd className="mono">{recovery.id}</dd>
          </div>
          <div>
            <dt>Target UID</dt>
            <dd className="mono">{recovery.target_uid}</dd>
          </div>
          <div className="kube-details__wide">
            <dt>Target image</dt>
            <dd className="mono">{recovery.target_image}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}

export function KubernetesPage({ view }: { view: View }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const workload = useQuery({
    queryKey: ["kubernetes-workloads"],
    queryFn: getKubernetesWorkloads,
    refetchInterval: 5000,
  });
  const recoveries = useQuery({
    queryKey: ["kubernetes-recoveries"],
    queryFn: getKubernetesRecoveries,
    enabled: workload.data?.enabled === true && view === "Runbooks",
    refetchInterval: 5000,
  });
  const recoveryEnabled = workload.data?.recovery_enabled ?? workload.data?.enabled ?? false;
  const cloud = workload.data?.environment === "temporary-eks";
  const [incident, setIncident] = useState("");
  const [run, setRun] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{
    text: string;
    error: boolean;
  } | null>(null);

  async function act(operation: () => Promise<unknown>) {
    if (busy || !recoveryEnabled) return;
    setBusy(true);
    setMessage(null);
    try {
      await operation();
      await recoveries.refetch();
      setMessage({
        text: "Request recorded. Follow its independently verified outcome below.",
        error: false,
      });
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : "Request failed",
        error: true,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page kube-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">{!workload.data ? "KUBERNETES" : cloud ? "TEMPORARY EKS" : "LOCAL KUBERNETES"}</p>
          <h1>{view}</h1>
          <p className="page-description">
            {view === "Runbooks"
              ? recoveryEnabled
                ? "Review a bounded recovery, approve it explicitly and inspect its verified outcome."
                : "Inspect recovery history. Operational actions are disabled in this environment."
              : "Independent observations of the demo worker. Updated every five seconds."}
          </p>
        </div>
      </header>
      {workload.isPending && (
        <div className="panel state-message" role="status">
          Loading workload observations…
        </div>
      )}
      {workload.isError && (
        <div className="error-panel" role="alert">
          Workload observations are unavailable.
        </div>
      )}
      {workload.data && !workload.data.enabled && (
        <div className="panel state-message" role="status">
          Kubernetes observation is disabled in this environment.
        </div>
      )}
      {workload.data?.enabled && workload.data.observations.length === 0 && (
        <div className="panel empty-state" role="status">
          <Boxes size={24} aria-hidden="true" />
          <strong>Waiting for the first independent observation.</strong>
        </div>
      )}
      {workload.data?.enabled &&
        workload.data.observations.map((observation) => (
          <WorkloadCard
            key={observation.name}
            observation={observation}
            view={view}
            now={now}
            unavailable={workload.isError}
            cloud={cloud}
          />
        ))}
      {view === "Runbooks" && workload.data?.enabled && (
        <>
          {recoveryEnabled ? (
          <section className="kube-runbook-grid" aria-label="Recovery proposal">
            <article className="panel kube-runbook">
              <div className="kube-runbook__heading">
                <span className="kube-icon">
                  <ShieldCheck size={22} aria-hidden="true" />
                </span>
                <Status>Manual approval</Status>
              </div>
              <h2>Restore one stopped demo worker</h2>
              <p>
                Start exactly one worker in{" "}
                <span className="mono">opsproof-demo</span>.
              </p>
              <h3>Required before approval</h3>
              <ul className="kube-prerequisites">
                <li>Supported firing queue incident</li>
                <li>Linked, active bounded queue experiment</li>
                <li>Fresh telemetry and a stopped worker</li>
                <li>KEDA disabled for this worker</li>
              </ul>
              <p className="kube-caption">
                The server checks eligibility before recording a proposal and
                again before execution. Approval expires after two minutes.
              </p>
            </article>
            <article className="panel kube-runbook">
              <h2>Review a recovery proposal</h2>
              <form
                className="kube-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void act(() => proposeKubernetesRecovery(incident, run));
                }}
              >
                <div className="field">
                  <label htmlFor="k8s-incident">Incident fingerprint</label>
                  <input
                    id="k8s-incident"
                    className="mono"
                    value={incident}
                    onChange={(event) => setIncident(event.target.value)}
                    required
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <div className="field">
                  <label htmlFor="k8s-run">Experiment ID</label>
                  <input
                    id="k8s-run"
                    className="mono"
                    value={run}
                    onChange={(event) => setRun(event.target.value)}
                    required
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <p className="field-help">
                  Use the incident and experiment IDs from the recorded queue
                  failure.
                </p>
                <button
                  className="button button--secondary"
                  disabled={busy}
                  type="submit"
                >
                  {busy ? "Recording request…" : "Review recovery proposal"}
                </button>
              </form>
            </article>
          </section>
          ) : (
            <article className="panel kube-runbook" role="status">
              <div className="kube-runbook__heading"><ShieldCheck size={22} aria-hidden="true" /><Status>Read-only</Status></div>
              <h2>Recovery actions are disabled</h2>
              <p>Workload observations and recorded outcomes remain available. This environment does not permit the local recovery runbook.</p>
            </article>
          )}
          {message && (
            <p
              className={message.error ? "error-panel" : "kube-notice"}
              role={message.error ? "alert" : "status"}
            >
              {message.text}
            </p>
          )}
          <section className="kube-history" aria-label="Recovery outcomes">
            <header className="kube-section-heading">
              <h2>Recovery outcomes</h2>
              <span className="kube-caption">
                Recorded proposals and verification results
              </span>
            </header>
            {recoveries.isPending && (
              <p role="status">Loading recovery records…</p>
            )}
            {recoveries.isError && (
              <p className="error-panel" role="alert">
                Recovery records are unavailable.
              </p>
            )}
            {recoveries.data?.length === 0 && (
              <div className="panel empty-state">
                <Clock3 size={23} aria-hidden="true" />
                <strong>No recovery proposals recorded</strong>
                <p>Recorded proposals and their outcomes will appear here.</p>
              </div>
            )}
            {recoveries.data?.map((recovery) => (
              <RecoveryCard
                key={recovery.id}
                recovery={recovery}
                now={now}
                busy={busy || recoveries.isError}
                canApprove={recoveryEnabled}
                approve={() =>
                  void act(() => approveKubernetesRecovery(recovery.id))
                }
              />
            ))}
          </section>
        </>
      )}
    </section>
  );
}
