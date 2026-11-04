import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Clock3,
  FileJson2,
  RefreshCw,
} from "lucide-react";

import { RunStatus } from "../components/RunStatus";
import {
  getExperiment,
  getExperimentEvents,
} from "../lib/api";
import {
  formatDate,
  isTerminal,
  shortId,
  titleCase,
} from "../lib/format";


export function ExperimentDetailPage() {
  const { runId } = useParams<{ runId: string }>();

  const run = useQuery({
    queryKey: ["experiment", runId],
    queryFn: () => getExperiment(runId ?? ""),
    enabled: Boolean(runId),
    retry: 1,

    refetchInterval: (query) =>
      isTerminal(query.state.data?.status ?? "")
        ? false
        : 2_000,
  });

  const events = useQuery({
    queryKey: ["experiment-events", runId],
    queryFn: () => getExperimentEvents(runId ?? ""),
    enabled: Boolean(runId),
    retry: 1,

    refetchInterval: isTerminal(run.data?.status ?? "")
      ? false
      : 2_000,
  });

  if (!runId) {
    return <p className="state-message">Invalid experiment.</p>;
  }

  return (
    <div className="page">
      <Link className="back-link" to="/experiments">
        <ArrowLeft size={16} />
        Back to experiments
      </Link>

      {run.isPending && (
        <p className="state-message" role="status">
          Loading experiment...
        </p>
      )}

      {run.isError && (
        <div className="error-panel" role="alert">
          <p>Could not retrieve this experiment.</p>

          <button
            className="button button--secondary"
            type="button"
            onClick={() => void run.refetch()}
          >
            <RefreshCw size={16} />
            Retry
          </button>
        </div>
      )}

      {run.data && (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">EXPERIMENT RECORD</p>
              <h1>{titleCase(run.data.scenario)}</h1>

              <p className="page-description mono">
                {run.data.id}
              </p>
            </div>

            <RunStatus status={run.data.status} />
          </div>

          <div className="detail-metrics">
            <div>
              <span>Submitted jobs</span>
              <strong>{run.data.count}</strong>
            </div>

            <div>
              <span>Job duration</span>
              <strong>{run.data.duration_ms} ms</strong>
            </div>

            <div>
              <span>Created</span>
              <strong>
                {formatDate(run.data.created_at)}
              </strong>
            </div>

            <div>
              <span>Completed</span>
              <strong>
                {formatDate(run.data.completed_at)}
              </strong>
            </div>
          </div>

          {run.data.status === "failed" && (
            <div className="error-panel" role="alert">
              <strong>Experiment failed</strong>
              <p>
                {run.data.error ??
                  "No failure explanation was recorded."}
              </p>
            </div>
          )}

          <div className="detail-grid">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Execution timeline</h2>
                  <p>
                    Events recorded by the OpsProof
                    control plane
                  </p>
                </div>

                <Clock3 size={18} className="muted" />
              </div>

              {events.isPending && (
                <p className="state-message" role="status">
                  Loading event history...
                </p>
              )}

              {events.isError && (
                <div className="error-panel" role="alert">
                  Event history is currently unavailable.
                </div>
              )}

              {events.data?.length === 0 && (
                <div className="empty-state">
                  <p>No events have been recorded.</p>
                </div>
              )}

              <ol className="event-timeline">
                {events.data?.map((event) => (
                  <li key={event.id} className="timeline-event">
                    <div
                      className="timeline-event__marker"
                      aria-hidden="true"
                    />

                    <div className="timeline-event__content">
                      <div className="timeline-event__header">
                        <strong>{titleCase(event.type)}</strong>
                        <time dateTime={event.created_at}>
                          {formatDate(event.created_at)}
                        </time>
                      </div>

                      <details className="evidence-details">
                        <summary>View recorded details</summary>

                        <pre>
                          {JSON.stringify(
                            event.details,
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Verified outcome</h2>
                  <p>Persisted experiment result</p>
                </div>

                <FileJson2 size={18} className="muted" />
              </div>

              {run.data.status === "succeeded" ? (
                <div className="outcome-success">
                  <strong>Verification succeeded</strong>
                  <p>
                    The control plane recorded a successful
                    outcome after its evidence checks.
                  </p>
                </div>
              ) : (
                <p className="muted">
                  {isTerminal(run.data.status)
                    ? "No successful outcome was recorded."
                    : "The experiment has not reached a verified terminal state."}
                </p>
              )}

              <div className="result-metadata">
                <span>Experiment ID</span>
                <code>{shortId(run.data.id)}</code>

                <span>Current state</span>
                <RunStatus status={run.data.status} />
              </div>

              <details className="evidence-details">
                <summary>Inspect raw result</summary>

                <pre>
                  {JSON.stringify(
                    run.data.result,
                    null,
                    2,
                  )}
                </pre>
              </details>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
