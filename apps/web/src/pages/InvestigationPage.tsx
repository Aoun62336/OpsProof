import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ShieldCheck,
} from "lucide-react";

import {
  approveRecovery,
  getCapabilities,
  getExperiments,
  getRecoveryEvents,
  listInvestigations,
  listRecoveries,
  proposeRecovery,
  rejectRecovery,
  requestAiEvaluation,
  requestInvestigation,
} from "../lib/api";

import {
  formatDate,
  shortId,
  titleCase,
} from "../lib/format";


const CONFIRM = "APPROVE DEMO WORKER RESUME";


export function InvestigationPage() {
  const { fingerprint = "" } = useParams<{
    fingerprint: string;
  }>();

  const queryClient = useQueryClient();

  const [runId, setRunId] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const investigationKey = useRef<string | null>(null);
  const recoveryKey = useRef<string | null>(null);

  const investigations = useQuery({
    queryKey: ["investigations", fingerprint],
    queryFn: () => listInvestigations(fingerprint),
    refetchInterval: 5_000,
  });

  const latest = investigations.isError ? undefined : investigations.data?.[0];

  const runs = useQuery({
    queryKey: ["experiments", 50],
    queryFn: () => getExperiments(50),
  });

  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: getCapabilities,
  });

  const recoveries = useQuery({
    queryKey: ["recoveries"],
    queryFn: listRecoveries,
    refetchInterval: 5_000,
  });

  const recovery = recoveries.isError ? undefined : recoveries.data?.find(
    (item) => item.investigation_id === latest?.id,
  );

  const events = useQuery({
    queryKey: ["recovery-events", recovery?.id],
    queryFn: () => getRecoveryEvents(recovery!.id),
    enabled: Boolean(recovery),
    refetchInterval: 5_000,
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["investigations", fingerprint] }),
      queryClient.invalidateQueries({ queryKey: ["recoveries"] }),
      queryClient.invalidateQueries({ queryKey: ["recovery-events"] }),
    ]);
  }
  const create = useMutation({
    mutationFn: () => {
      investigationKey.current ??= crypto.randomUUID();
      return requestInvestigation(fingerprint, runId || null, investigationKey.current);
    },
    onSuccess: async () => { investigationKey.current = null; recoveryKey.current = null; await refresh(); },
  });
  const ai = useMutation({ mutationFn: () => requestAiEvaluation(latest!.id), onSuccess: refresh });
  const propose = useMutation({
    mutationFn: () => {
      recoveryKey.current ??= crypto.randomUUID();
      return proposeRecovery(latest!.id, recoveryKey.current);
    },
    onSuccess: async () => { recoveryKey.current = null; await refresh(); },
  });
  const approve = useMutation({ mutationFn: () => approveRecovery(recovery!.id),
    onSuccess: async () => { setConfirmation(""); await refresh(); } });
  const reject = useMutation({ mutationFn: () => rejectRecovery(recovery!.id), onSuccess: refresh });
  const snapshot = latest?.snapshot;
  const baseline = latest?.baseline;
  const allowed = !investigations.isError && latest?.status === "ready"
    && baseline?.action === "resume_demo_worker";
  const error = [create, ai, propose, approve, reject].find((mutation) => mutation.isError)?.error;
  return (
    <div className="page investigation-page">
      <Link className="back-link" to="/incidents"><ArrowLeft size={16} />Back to incidents</Link>
      <header className="page-header"><div>
        <p className="overline">INCIDENT INVESTIGATION / LOCAL</p>
        <h1>Investigation</h1>
        <p className="page-description">Collect evidence, review a diagnosis, and approve only the supported demo recovery.</p>
      </div></header>
      {error && <p role="alert" className="inline-error">{error.message}</p>}
      {(capabilities.isError || recoveries.isError || runs.isError || events.isError) &&
        <p role="alert" className="inline-error">Some operational records are unavailable. Retry after checking the control API.</p>}
      <div className="investigation-layout">
        <section className="panel">
          <div className="panel-header"><div><p className="overline">01 / EVIDENCE</p>
            <h2>Evidence snapshot</h2><p>Bounded observations from the evidence worker</p>
          </div></div>
          <label className="investigation-label" htmlFor="linked-run">Linked experiment</label>
          <select id="linked-run" className="investigation-select" value={runId}
            disabled={create.isPending} onChange={(event) => {
              setRunId(event.target.value); investigationKey.current = null; create.reset();
            }}>
            <option value="">No linked experiment</option>
            {runs.data?.filter((run) => run.status === "verifying" && run.scenario === "queue-burst").map((run) => (
              <option key={run.id} value={run.id}>
                {run.scenario} · {shortId(run.id)}
              </option>
            ))}
          </select>

          <p className="scope-note">
            Link a currently verifying queue-burst run
            to enable exact-job recovery verification.
            Other incidents can be diagnosed without a run.
          </p>

          <button
            type="button"
            className="button button--primary"
            disabled={create.isPending || !fingerprint}
            onClick={() => create.mutate()}
          >
            {create.isPending
              ? "Recording…"
              : "Start investigation"}
          </button>

          {investigations.isError && (
            <p className="inline-error" role="alert">
              Investigation records unavailable.
            </p>
          )}

          {latest && (
            <div className="investigation-summary">
              <p className="overline">
                LATEST INVESTIGATION
              </p>

              <strong>
                {titleCase(latest.status)}
              </strong>

              <span className="mono">
                {shortId(latest.id)} ·{" "}
                {formatDate(latest.created_at)}
              </span>

              {latest.error && (
                <p className="inline-error">
                  {latest.error}
                </p>
              )}

              {snapshot && (
                <dl className="fact-list">
                  <dt>Alert</dt>
                  <dd>
                    {String(
                      snapshot.alert_name ?? "Unavailable",
                    )}
                  </dd>

                  <dt>Scrape verified</dt>
                  <dd>
                    {snapshot.scrape_fresh === true
                      ? "Yes"
                      : "No"}
                  </dd>

                  <dt>Worker hold</dt>
                  <dd>
                    {snapshot.worker_paused === true
                      ? "Confirmed"
                      : snapshot.worker_paused === false
                        ? "Not active"
                        : "Unknown"}
                  </dd>

                  <dt>Queued jobs</dt>
                  <dd>
                    {typeof snapshot.queued === "number"
                      ? snapshot.queued
                      : "Unknown"}
                  </dd>

                  <dt>Observed at</dt>
                  <dd>
                    {typeof snapshot.observed_at === "string"
                      ? formatDate(snapshot.observed_at)
                      : "Not recorded"}
                  </dd>
                </dl>
              )}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="overline">
                02 / DIAGNOSE
              </p>

              <h2>Deterministic baseline</h2>

              <p>
                Auditable rules before model output
              </p>
            </div>

            <ShieldCheck
              size={20}
              aria-hidden="true"
            />
          </div>

          {baseline && latest?.status === "ready" ? (
            <div className="diagnosis-result">
              <strong>
                {titleCase(
                  String(baseline.cause ?? "unknown"),
                )}
              </strong>

              <p>
                {String(
                  baseline.explanation
                  ?? "No explanation recorded",
                )}
              </p>

              <span>
                Recommendation:{" "}
                {String(baseline.action ?? "none")}
              </span>
            </div>
          ) : (
            <p className="state-message">
              A completed evidence snapshot is required.
            </p>
          )}

          <div className="ai-panel">
            <p className="overline">
              OPTIONAL MODEL EVALUATION
            </p>

            <p>
              AI output is an untrusted hypothesis
              and cannot authorize recovery.
            </p>

            {(!capabilities.isError && capabilities.data?.ai_enabled)
              && latest?.status === "ready"
              && latest.ai_status === "not_requested"
              && (
                <button
                  type="button"
                  className="button button--secondary"
                  disabled={ai.isPending}
                  onClick={() => ai.mutate()}
                >
                  Evaluate model once
                </button>
              )}

            {!(!capabilities.isError && capabilities.data?.ai_enabled) && (
              <p className="scope-note">
                Paid model calls are disabled.
              </p>
            )}

            {latest && latest.ai_status !== "not_requested" && (
              <p>
                Model status: {latest?.ai_status}
              </p>
            )}

            {latest?.ai_result && (
              <div className="diagnosis-result">
                <strong>
                  {titleCase(
                    String(latest.ai_result.cause),
                  )}
                </strong>

                <p>
                  {String(
                    latest.ai_result.explanation ?? "",
                  )}
                </p>

                <small>
                  Hypothesis only ·{" "}
                  {latest.ai_provider} /{" "}
                  {latest.ai_model}
                </small>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="panel recovery-panel">
        <div className="panel-header">
          <div>
            <p className="overline">
              03 / CONTROLLED ACTION
            </p>

            <h2>Demo-worker recovery</h2>

            <p>
              Policy-allowlisted, explicit approval,
              independent verification
            </p>
          </div>
        </div>

        {!(!capabilities.isError && capabilities.data?.recovery_enabled) && (
          <p className="recovery-warning">
            <AlertTriangle size={17} />
            Recovery kill switch is off.
            No action can execute.
          </p>
        )}

        {allowed
          && !recovery
          && (!capabilities.isError && capabilities.data?.recovery_enabled)
          && (
            <button
              type="button"
              className="button button--secondary"
              onClick={() => propose.mutate()}
              disabled={propose.isPending}
            >
              Propose worker resume
            </button>
          )}

        {!allowed && (
          <p className="scope-note">
            An eligible, recent deterministic diagnosis
            is required. AI cannot change this requirement.
          </p>
        )}

        {recovery && (
          <div className="recovery-summary">
            <div className="recovery-meta">
              <strong>
                {titleCase(recovery.status)}
              </strong>

              <span className="mono">
                {shortId(recovery.id)}
              </span>

              <span>
                Expires:{" "}
                {formatDate(recovery.expires_at)}
              </span>
            </div>

            {recovery.status === "pending_approval" && (
              <div className="approval-form">
                <label htmlFor="confirmation">
                  Type <strong>{CONFIRM}</strong> to approve
                  this specific demo action
                </label>

                <input
                  id="confirmation"
                  value={confirmation}
                  onChange={(event) =>
                    setConfirmation(event.target.value)
                  }
                  autoComplete="off"
                />

                <div className="approval-actions">
                  <button
                    className="button button--primary"
                    type="button"
                    disabled={
                      confirmation !== CONFIRM
                      || approve.isPending
                      || capabilities.isError || !capabilities.data?.recovery_enabled
                    }
                    onClick={() => approve.mutate()}
                  >
                    Approve once
                  </button>

                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={reject.isPending}
                    onClick={() => reject.mutate()}
                  >
                    Reject
                  </button>
                </div>
              </div>
            )}

            {recovery.error && (
              <p className="inline-error">
                {recovery.error}
              </p>
            )}

            {recovery.status === "succeeded" && (
              <p className="verified-note">
                <CheckCircle2 size={17} />
                Exact jobs, experiment verification,
                and alert resolution were checked.
              </p>
            )}

            {events.data && events.data.length > 0 && (
              <ol className="recovery-events">
                {events.data.map((event) => (
                  <li key={event.id}>
                    <strong>
                      {titleCase(event.type)}
                    </strong>

                    <time dateTime={event.created_at}>
                      {formatDate(event.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
