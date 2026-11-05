import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  ArrowRight,
  Clock3,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

import { RunStatus } from "../components/RunStatus";

import {
  getSummary,
  getExperimentEvents,
} from "../lib/api";

import {
  formatDate,
  shortId,
  titleCase,
} from "../lib/format";

export function OverviewPage() {
  const summary = useQuery({
    queryKey: ["overview"],
    queryFn: getSummary,
    refetchInterval: 15_000,
    retry: 1,
  });

  // Do not display cached measurements as current
  // when the last request has failed.
  const data = summary.isError
    ? undefined
    : summary.data;

  const active = data
    ? data.counts.queued +
      data.counts.running +
      data.counts.verifying
    : 0;

  const latestVerified = data?.recent.find(
    (run) => run.status === "succeeded",
  );

  const trail = useQuery({
    queryKey: [
      "experiment-events",
      latestVerified?.id,
    ],

    queryFn: () =>
      getExperimentEvents(latestVerified!.id),

    enabled: Boolean(latestVerified),
    staleTime: 60_000,
    retry: 1,
  });

  const hasAttention = Boolean(
    data &&
      (active > 0 || data.counts.failed > 0),
  );

  return (
    <div className="page overview-page">
      <header className="page-header">
        <div>
          <p className="overline">
            CONTROL PLANE / LOCAL
          </p>

          <h1>Operations</h1>

          <p className="page-description">
            Current work, recorded outcomes, and the
            evidence behind them.
          </p>
        </div>

        <Link
          className="button button--primary"
          to="/experiments"
        >
          New experiment
          <ArrowRight
            size={17}
            aria-hidden="true"
          />
        </Link>
      </header>

      {summary.isPending && (
        <p className="state-message" role="status">
          Loading operational records…
        </p>
      )}

      {summary.isError && (
        <div className="error-panel" role="alert">
          <AlertTriangle
            size={19}
            aria-hidden="true"
          />

          <div>
            <strong>Records unavailable</strong>

            <p>
              Could not reach the control API.
              No operational status can be inferred.
            </p>
          </div>

          <button
            className="button button--secondary"
            onClick={() => void summary.refetch()}
            type="button"
          >
            <RefreshCw size={16} />
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <section
            className="attention"
            aria-labelledby="attention-title"
          >
            <div className="attention__heading">
              <p className="overline overline--light">
                OPERATIONAL PRIORITY
              </p>

              <h2 id="attention-title">
                {hasAttention
                  ? "Work requiring review"
                  : "No unresolved experiment records"}
              </h2>

              <p>
                {hasAttention
                  ? "Review active or unsuccessful experiments before proceeding with new changes."
                  : "This describes recorded experiment states only, not the health of unconnected infrastructure."}
              </p>
            </div>

            <div className="attention__summary">
              <div>
                <span>Active runs</span>
                <strong>{active}</strong>
              </div>

              <div>
                <span>Failed runs</span>
                <strong>{data.counts.failed}</strong>
              </div>

              <Link to="/experiments">
                Inspect experiments
                <ArrowRight
                  size={15}
                  aria-hidden="true"
                />
              </Link>
            </div>
          </section>

          <section
            className="metrics-row"
            aria-label="Recorded experiment summary"
          >
            <div>
              <span>All recorded</span>
              <strong>
                {data.total.toLocaleString()}
              </strong>
              <small>Experiment records</small>
            </div>

            <div>
              <span>Verified</span>
              <strong>
                {data.counts.succeeded.toLocaleString()}
              </strong>
              <small>Successful outcomes</small>
            </div>

            <div>
              <span>Awaiting execution</span>
              <strong>
                {data.counts.queued.toLocaleString()}
              </strong>
              <small>Queued runs</small>
            </div>

            <div>
              <span>Evidence snapshot</span>
              <strong className="metrics-row__date">
                {formatDate(data.generated_at)}
              </strong>
              <small>Last API response</small>
            </div>
          </section>

          <div className="overview-columns">
            <section
              className="panel activity-panel"
              aria-labelledby="activity-title"
            >
              <div className="panel-header">
                <div>
                  <p className="overline">
                    01 / ACTIVITY
                  </p>

                  <h2 id="activity-title">
                    Recent experiments
                  </h2>

                  <p>
                    Latest records from the
                    control-plane database
                  </p>
                </div>

                <Link
                  className="subtle-link"
                  to="/experiments"
                >
                  See all
                  <ArrowRight size={16} />
                </Link>
              </div>

              {data.recent.length === 0 ? (
                <div className="empty-state">
                  <Clock3
                    size={25}
                    aria-hidden="true"
                  />

                  <strong>No runs recorded</strong>

                  <p>
                    Create an experiment to begin
                    collecting evidence.
                  </p>

                  <Link to="/experiments">
                    Open experiments
                  </Link>
                </div>
              ) : (
                <div className="activity-list">
                  {data.recent.map((run) => (
                    <Link
                      to={`/experiments/${run.id}`}
                      key={run.id}
                      className="activity-row"
                    >
                      <div className="activity-row__identity">
                        <strong>
                          {titleCase(run.scenario)}
                        </strong>

                        <small className="mono">
                          {shortId(run.id)} ·{" "}
                          {formatDate(run.created_at)}
                        </small>
                      </div>

                      <RunStatus status={run.status} />

                      <ArrowRight
                        size={17}
                        className="activity-row__arrow"
                        aria-hidden="true"
                      />
                    </Link>
                  ))}
                </div>
              )}
            </section>

            <section
              className="panel verification-panel"
              aria-labelledby="trail-title"
            >
              <div className="panel-header">
                <div>
                  <p className="overline">
                    02 / EVIDENCE
                  </p>

                  <h2 id="trail-title">
                    Verification trail
                  </h2>

                  <p>
                    Events recorded by the
                    independent workers
                  </p>
                </div>

                <ShieldCheck
                  size={21}
                  aria-hidden="true"
                />
              </div>

              {!latestVerified && (
                <div className="empty-state empty-state--left">
                  <p>
                    No successfully verified experiment
                    appears in the latest records.
                  </p>
                </div>
              )}

              {latestVerified && (
                <>
                  <div className="verification-reference">
                    <span>LATEST VERIFIED RUN</span>

                    <strong className="mono">
                      {shortId(latestVerified.id)}
                    </strong>

                    <RunStatus
                      status={latestVerified.status}
                    />
                  </div>

                  {trail.isPending && (
                    <p
                      className="state-message"
                      role="status"
                    >
                      Loading event history…
                    </p>
                  )}

                  {trail.isError && (
                    <p
                      className="inline-error"
                      role="alert"
                    >
                      Event history is unavailable;
                      verification details could not
                      be retrieved.
                    </p>
                  )}

                  {trail.data && (
                    <ol className="verification-trail">
                      {trail.data.slice(-4).map((item) => (
                        <li key={item.id}>
                          <span
                            className="trail-dot"
                            aria-hidden="true"
                          />

                          <div>
                            <strong>
                              {titleCase(item.type)}
                            </strong>

                            <time dateTime={item.created_at}>
                              {formatDate(item.created_at)}
                            </time>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}

                  <Link
                    className="subtle-link"
                    to={`/experiments/${latestVerified.id}`}
                  >
                    Inspect full evidence
                    <ExternalLink
                      size={15}
                      aria-hidden="true"
                    />
                  </Link>
                </>
              )}
            </section>
          </div>

          <p className="scope-note">
            <span aria-hidden="true">◦</span>{" "}
            Scope: local experiment records only.
            Kubernetes, incident detection and cloud
            telemetry are not yet connected.
          </p>
        </>
      )}
    </div>
  );
}
