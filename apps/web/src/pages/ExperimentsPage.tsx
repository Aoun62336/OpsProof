import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Link,
  useNavigate,
} from "react-router-dom";

import {
  ArrowRight,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { RunStatus } from "../components/RunStatus";

import {
  createExperiment,
  getExperiments,
} from "../lib/api";

import {
  formatDate,
  shortId,
  titleCase,
} from "../lib/format";

import type {
  CreateExperiment,
  RunStatus as Status,
} from "../lib/types";

const statuses: Status[] = [
  "queued",
  "running",
  "verifying",
  "succeeded",
  "failed",
];

export function ExperimentsPage() {
  const [count, setCount] = useState(5);
  const [duration, setDuration] = useState(250);
  const [filter, setFilter] = useState("all");

  const pendingKey = useRef<string | null>(null);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

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

      const payload: CreateExperiment = {
        scenario: "queue-burst",
        count,
        duration_ms: duration,
      };

      return createExperiment(
        payload,
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

  const visible = (
    runs.isError ? [] : runs.data ?? []
  ).filter(
    (run) =>
      filter === "all" || run.status === filter,
  );

  function changeParams(update: () => void) {
    pendingKey.current = null;
    create.reset();
    update();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (create.isPending) return;

    if (
      !Number.isInteger(count) ||
      count < 1 ||
      count > 8
    ) {
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

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="overline">
            CONTROLLED EXECUTION
          </p>

          <h1>Experiments</h1>

          <p className="page-description">
            Run bounded scenarios. Review the recorded
            outcome, not just the action.
          </p>
        </div>
      </header>

      <div className="experiments-layout">
        <section
          className="panel experiment-config"
          aria-labelledby="new-run-title"
        >
          <div className="panel-header">
            <div>
              <p className="overline">
                01 / CREATE
              </p>

              <h2 id="new-run-title">
                New experiment
              </h2>

              <p>Local sandbox only</p>
            </div>

            <FlaskConical
              size={21}
              aria-hidden="true"
            />
          </div>

          <form
            className="experiment-form"
            onSubmit={submit}
          >
            <div className="field">
              <label htmlFor="scenario">
                Scenario
              </label>

              <input
                id="scenario"
                value="queue-burst"
                readOnly
                aria-describedby="scenario-note"
              />

              <p
                id="scenario-note"
                className="field-help"
              >
                Submit bounded jobs to the demo workload.
              </p>
            </div>

            <div className="form-two-col">
              <div className="field">
                <label htmlFor="job-count">
                  Job count
                </label>

                <input
                  id="job-count"
                  type="number"
                  min="1"
                  max="8"
                  step="1"
                  value={count}
                  required
                  onChange={(event) =>
                    changeParams(() =>
                      setCount(Number(event.target.value)),
                    )
                  }
                />

                <p className="field-help">
                  1–8 jobs
                </p>
              </div>

              <div className="field">
                <label htmlFor="duration">
                  Duration per job
                </label>

                <input
                  id="duration"
                  type="number"
                  min="50"
                  max="750"
                  step="1"
                  value={duration}
                  required
                  onChange={(event) =>
                    changeParams(() =>
                      setDuration(
                        Number(event.target.value),
                      ),
                    )
                  }
                />

                <p className="field-help">
                  50–750 ms
                </p>
              </div>
            </div>

            <div className="safety-note">
              <ShieldCheck
                size={18}
                aria-hidden="true"
              />

              <p>
                <strong>Execution boundary</strong>

                <span>
                  No Kubernetes changes, shell execution
                  or fault injection. This is a controlled
                  demo workload.
                </span>
              </p>
            </div>

            {create.isError && (
              <p className="inline-error" role="alert">
                {create.error instanceof Error
                  ? create.error.message
                  : "Could not submit experiment."}
              </p>
            )}

            <button
              className="button button--primary button--full"
              type="submit"
              disabled={create.isPending}
            >
              {create.isPending
                ? "Submitting…"
                : "Run experiment"}

              <ArrowRight
                size={17}
                aria-hidden="true"
              />
            </button>
          </form>
        </section>

        <section
          className="panel experiment-history"
          aria-labelledby="history-title"
        >
          <div className="panel-header">
            <div>
              <p className="overline">
                02 / HISTORY
              </p>

              <h2 id="history-title">
                Recorded runs
              </h2>

              <p>
                Most recent 50 experiments
              </p>
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
              Status
            </label>

            <select
              id="status-filter"
              value={filter}
              onChange={(event) =>
                setFilter(event.target.value)
              }
            >
              <option value="all">
                All states
              </option>

              {statuses.map((status) => (
                <option key={status} value={status}>
                  {titleCase(status)}
                </option>
              ))}
            </select>
          </div>

          {runs.isPending && (
            <p className="state-message" role="status">
              Loading experiments…
            </p>
          )}

          {runs.isError && (
            <div className="error-panel" role="alert">
              <p>
                Experiment history is unavailable.
              </p>

              <button
                className="button button--secondary"
                type="button"
                onClick={() => void runs.refetch()}
              >
                Retry
              </button>
            </div>
          )}

          {runs.isSuccess && visible.length === 0 && (
            <div className="empty-state">
              <FlaskConical size={24} />

              <strong>No matching runs</strong>

              <p>
                Start an experiment or change
                the status filter.
              </p>
            </div>
          )}

          {visible.length > 0 && (
            <div className="activity-list activity-list--inside">
              {visible.map((run) => (
                <Link
                  key={run.id}
                  className="activity-row"
                  to={`/experiments/${run.id}`}
                >
                  <span className="activity-row__identity">
                    <strong>
                      {titleCase(run.scenario)}
                    </strong>

                    <small className="mono">
                      {shortId(run.id)} ·{" "}
                      {formatDate(run.created_at)}
                    </small>
                  </span>

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
      </div>
    </div>
  );
}
