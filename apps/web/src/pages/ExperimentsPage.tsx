import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  FlaskConical,
  RefreshCw,
} from "lucide-react";

import { RunStatus } from "../components/RunStatus";
import {
  createExperiment,
  getExperiments,
} from "../lib/api";
import { formatDate, shortId } from "../lib/format";
import type { RunStatus as RunStatusType } from "../lib/types";


export function ExperimentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [count, setCount] = useState(5);
  const [duration, setDuration] = useState(250);
  const [filter, setFilter] = useState("all");

  // Preserve the same key when retrying an ambiguous request.
  const pendingKey = useRef<string | null>(null);

  const runs = useQuery({
    queryKey: ["experiments", 50],
    queryFn: () => getExperiments(50),
    refetchInterval: 15_000,
    retry: 1,
  });

  const create = useMutation({
    mutationFn: () => {
      if (!pendingKey.current) {
        pendingKey.current = crypto.randomUUID();
      }

      return createExperiment(
        {
          scenario: "queue-burst",
          count,
          duration_ms: duration,
        },
        pendingKey.current,
      );
    },

    onSuccess: async (experiment) => {
      pendingKey.current = null;

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["experiments"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["overview"],
        }),
      ]);

      navigate(`/experiments/${experiment.id}`);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!Number.isInteger(count) || count < 1 || count > 8) {
      return;
    }

    if (
      !Number.isInteger(duration) ||
      duration < 50 ||
      duration > 750
    ) {
      return;
    }

    create.mutate();
  }

  const filtered = (runs.data ?? []).filter(
    (run) => filter === "all" || run.status === filter,
  );

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">RELIABILITY EXPERIMENTS</p>
          <h1>Controlled tests. Verifiable outcomes.</h1>
          <p className="page-description">
            Execute bounded scenarios and preserve the evidence
            behind each result.
          </p>
        </div>
      </div>

      <div className="experiment-grid">
        <section className="panel experiment-config">
          <div className="panel-header">
            <div>
              <h2>New experiment</h2>
              <p>Currently supported sandbox scenario</p>
            </div>
            <FlaskConical size={20} className="muted" />
          </div>

          <form className="experiment-form" onSubmit={submit}>
            <div className="field">
              <label htmlFor="scenario">
                Scenario
              </label>

              <input
                id="scenario"
                value="queue-burst"
                readOnly
                aria-describedby="scenario-help"
              />

              <p id="scenario-help" className="field-help">
                Submits background jobs to the isolated
                demonstration workload.
              </p>
            </div>

            <div className="field">
              <label htmlFor="job-count">
                Job count
              </label>

              <input
                id="job-count"
                type="number"
                min={1}
                max={8}
                step={1}
                value={count}
                onChange={(event) => {
                  setCount(Number(event.target.value));
                  pendingKey.current = null;
                }}
                required
              />
            </div>

            <div className="field">
              <label htmlFor="duration">
                Processing duration (ms)
              </label>

              <input
                id="duration"
                type="number"
                min={50}
                max={750}
                step={1}
                value={duration}
                onChange={(event) => {
                  setDuration(Number(event.target.value));
                  pendingKey.current = null;
                }}
                required
              />
            </div>

            <div className="execution-note">
              <strong>Execution boundary</strong>
              <p>
                This scenario submits bounded demonstration
                jobs. It does not modify Kubernetes resources
                or perform fault injection.
              </p>
            </div>

            {create.isError && (
              <p className="inline-error" role="alert">
                {create.error instanceof Error
                  ? create.error.message
                  : "Could not create experiment."}
              </p>
            )}

            <button
              className="button button--primary"
              type="submit"
              disabled={create.isPending}
            >
              <FlaskConical size={17} />
              {create.isPending
                ? "Submitting..."
                : "Run experiment"}
            </button>
          </form>
        </section>

        <section className="panel experiment-history">
          <div className="panel-header">
            <div>
              <h2>Experiment history</h2>
              <p>Latest 50 records from PostgreSQL</p>
            </div>

            <button
              type="button"
              className="icon-button"
              aria-label="Refresh experiments"
              onClick={() => void runs.refetch()}
            >
              <RefreshCw size={17} />
            </button>
          </div>

          <div className="table-toolbar">
            <label htmlFor="status-filter">
              Filter status
            </label>

            <select
              id="status-filter"
              value={filter}
              onChange={(event) =>
                setFilter(event.target.value)
              }
            >
              <option value="all">All statuses</option>
              {(
                [
                  "queued",
                  "running",
                  "verifying",
                  "succeeded",
                  "failed",
                ] as RunStatusType[]
              ).map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          {runs.isPending && (
            <p className="state-message" role="status">
              Loading experiments...
            </p>
          )}

          {runs.isError && (
            <div className="error-panel" role="alert">
              Could not load experiment history.
            </div>
          )}

          {runs.isSuccess && filtered.length === 0 && (
            <div className="empty-state">
              <FlaskConical size={24} />
              <h3>No matching experiments</h3>
              <p>
                Create a new run or change the status filter.
              </p>
            </div>
          )}

          {filtered.length > 0 && (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Run</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col">
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {filtered.map((run) => (
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
                          aria-label={`Open experiment ${shortId(run.id)}`}
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
      </div>
    </div>
  );
}
