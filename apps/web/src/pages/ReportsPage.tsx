import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  ArrowRight,
  Download,
  FileJson2,
  RefreshCw,
} from "lucide-react";

import { RunStatus } from "../components/RunStatus";

import {
  getExperimentEvents,
  getExperiments,
} from "../lib/api";

import {
  formatDate,
  isTerminal,
  shortId,
  titleCase,
} from "../lib/format";

import type { Experiment } from "../lib/types";

export function ReportsPage() {
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState<
    string | null
  >(null);

  const runs = useQuery({
    queryKey: ["report-experiments"],
    queryFn: () => getExperiments(50),
    retry: 1,
  });

  const completed = (
    runs.isError ? [] : runs.data ?? []
  ).filter((run) => isTerminal(run.status));

  async function exportReport(run: Experiment) {
    setExporting(run.id);
    setExportError("");

    try {
      const events = await getExperimentEvents(run.id);

      const report = {
        schema_version: "opsproof-evidence/v1",
        source: "local-control-plane",
        exported_at: new Date().toISOString(),
        experiment: run,
        events,
      };

      const blob = new Blob(
        [JSON.stringify(report, null, 2)],
        {
          type: "application/json",
        },
      );

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download = `opsproof-${shortId(run.id)}.json`;

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      window.setTimeout(
        () => URL.revokeObjectURL(url),
        1_000,
      );
    } catch {
      setExportError(
        "Evidence export failed. Check the control API and retry.",
      );
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="overline">
            AUDIT & EVIDENCE
          </p>

          <h1>Evidence archive</h1>

          <p className="page-description">
            Inspectable results, including
            unsuccessful experiments.
          </p>
        </div>
      </header>

      <section
        className="panel"
        aria-labelledby="reports-title"
      >
        <div className="panel-header">
          <div>
            <p className="overline">
              RECORDED OUTCOMES
            </p>

            <h2 id="reports-title">
              Completed and failed runs
            </h2>

            <p>
              Terminal records among the latest
              50 experiments
            </p>
          </div>

          <button
            className="icon-button"
            type="button"
            aria-label="Refresh reports"
            onClick={() => void runs.refetch()}
          >
            <RefreshCw size={18} />
          </button>
        </div>

        {exportError && (
          <p className="inline-error" role="alert">
            {exportError}
          </p>
        )}

        {runs.isPending && (
          <p className="state-message" role="status">
            Loading evidence…
          </p>
        )}

        {runs.isError && (
          <div className="error-panel" role="alert">
            Evidence records are unavailable.

            <button
              type="button"
              className="button button--secondary"
              onClick={() => void runs.refetch()}
            >
              Retry
            </button>
          </div>
        )}

        {runs.isSuccess && completed.length === 0 && (
          <div className="empty-state">
            <FileJson2 size={24} />

            <strong>No completed records</strong>

            <p>
              Completed or failed experiments
              will appear here.
            </p>
          </div>
        )}

        {completed.length > 0 && (
          <div className="report-list">
            {completed.map((run) => (
              <div className="report-row" key={run.id}>
                <div className="report-row__identity">
                  <Link
                    to={`/experiments/${run.id}`}
                    className="report-row__title"
                  >
                    {titleCase(run.scenario)}

                    <ArrowRight
                      size={14}
                      aria-hidden="true"
                    />
                  </Link>

                  <small className="mono">
                    {shortId(run.id)} ·{" "}
                    {formatDate(run.completed_at)}
                  </small>
                </div>

                <RunStatus status={run.status} />

                <button
                  className="button button--secondary button--small"
                  type="button"
                  onClick={() => void exportReport(run)}
                  disabled={exporting === run.id}
                >
                  <Download
                    size={15}
                    aria-hidden="true"
                  />

                  {exporting === run.id
                    ? "Exporting…"
                    : "Export JSON"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="scope-note">
        Exports preserve the current API record and event
        history. They are not signed or immutable evidence
        archives.
      </p>
    </div>
  );
}
