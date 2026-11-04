import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  Layers3,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";

import { RunStatus } from "../components/RunStatus";
import { getSummary } from "../lib/api";
import { formatDate, shortId } from "../lib/format";


export function OverviewPage() {
  const query = useQuery({
    queryKey: ["overview"],
    queryFn: getSummary,
    refetchInterval: 15_000,
    retry: 1,
  });

  const data = query.data;

  const active = data
    ? data.counts.queued +
      data.counts.running +
      data.counts.verifying
    : 0;

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">OPERATIONS OVERVIEW</p>
          <h1>Know what failed. Prove what recovered.</h1>
          <p className="page-description">
            Investigate with evidence. Operate with control.
          </p>
        </div>

        <Link
          className="button button--primary"
          to="/experiments"
        >
          <FlaskConical size={17} aria-hidden="true" />
          New experiment
        </Link>
      </div>

      <div className="environment-banner">
        <div className="environment-banner__icon">
          <Layers3 size={20} aria-hidden="true" />
        </div>

        <div>
          <strong>Local control-plane workspace</strong>
          <p>
            Dashboard measurements come from recorded
            experiment state. Kubernetes telemetry is not
            connected to this view yet.
          </p>
        </div>

        <span className="environment-banner__label">
          DEVELOPMENT
        </span>
      </div>

      {query.isPending && (
        <p className="state-message" role="status">
          Loading recorded experiment data...
        </p>
      )}

      {query.isError && (
        <div className="error-panel" role="alert">
          <CircleAlert size={20} aria-hidden="true" />

          <div>
            <strong>Could not retrieve the overview.</strong>
            <p>
              Check the control API and its database connection.
            </p>
          </div>

          <button
            type="button"
            className="button button--secondary"
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={15} />
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <div className="metric-grid">
            <Metric
              label="Recorded experiments"
              value={data.total}
              description="All stored experiment records"
              icon={<Layers3 size={19} />}
            />

            <Metric
              label="Succeeded"
              value={data.counts.succeeded}
              description="Completed with successful verification"
              icon={<CheckCircle2 size={19} />}
              tone="positive"
            />

            <Metric
              label="In progress"
              value={active}
              description="Queued, running or verifying"
              icon={<FlaskConical size={19} />}
            />

            <Metric
              label="Failed"
              value={data.counts.failed}
              description="Recorded unsuccessful runs"
              icon={<CircleAlert size={19} />}
              tone="critical"
            />
          </div>

          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Recent experiments</h2>
                  <p>
                    Latest recorded execution and verification
                    outcomes
                  </p>
                </div>

                <Link
                  className="text-link"
                  to="/experiments"
                >
                  View all
                  <ArrowRight size={15} />
                </Link>
              </div>

              {data.recent.length === 0 ? (
                <div className="empty-state">
                  <FlaskConical size={24} />

                  <h3>No experiments recorded</h3>

                  <p>
                    Start a controlled experiment to create
                    the first evidence record.
                  </p>

                  <Link to="/experiments">
                    Open experiment console
                  </Link>
                </div>
              ) : (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Experiment</th>
                        <th scope="col">Status</th>
                        <th scope="col">Created</th>
                        <th scope="col">
                          <span className="sr-only">Open</span>
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {data.recent.map((run) => (
                        <tr key={run.id}>
                          <td>
                            <span className="table-primary">
                              {run.scenario}
                            </span>
                            <span className="table-secondary mono">
                              {shortId(run.id)}
                            </span>
                          </td>

                          <td>
                            <RunStatus status={run.status} />
                          </td>

                          <td className="muted">
                            {formatDate(run.created_at)}
                          </td>

                          <td>
                            <Link
                              className="row-link"
                              to={`/experiments/${run.id}`}
                              aria-label={`View experiment ${shortId(run.id)}`}
                            >
                              <ArrowRight size={17} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="panel context-panel">
              <div className="panel-header">
                <div>
                  <h2>Operational context</h2>
                  <p>Current integration coverage</p>
                </div>
              </div>

              <div className="context-item">
                <span className="context-item__label">
                  Control-plane data
                </span>
                <strong className="text-success">
                  Available
                </strong>
              </div>

              <div className="context-item">
                <span className="context-item__label">
                  Kubernetes telemetry
                </span>
                <strong className="muted">
                  Not connected
                </strong>
              </div>

              <div className="context-item">
                <span className="context-item__label">
                  Incident detection
                </span>
                <strong className="muted">
                  Not connected
                </strong>
              </div>

              <div className="context-item">
                <span className="context-item__label">
                  Evidence snapshot
                </span>
                <strong className="mono context-date">
                  {formatDate(data.generated_at)}
                </strong>
              </div>

              <p className="context-footnote">
                Unavailable telemetry is never interpreted as
                healthy service status.
              </p>
            </section>
          </div>
        </>
      )}
    </div>
  );
}


function Metric({
  label,
  value,
  description,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: number;
  description: string;
  icon: ReactNode;
  tone?: "neutral" | "positive" | "critical";
}) {
  return (
    <section className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__top">
        <span>{label}</span>
        <span className="metric-card__icon" aria-hidden="true">
          {icon}
        </span>
      </div>

      <strong className="metric-card__value">
        {value.toLocaleString()}
      </strong>

      <p>{description}</p>
    </section>
  );
}
