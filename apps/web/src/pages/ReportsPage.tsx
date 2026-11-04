import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
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
} from "../lib/format";


export function ReportsPage() {
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["report-experiments"],
    queryFn: () => getExperiments(50),
    retry: 1,
  });

  const completedRuns = (query.data ?? []).filter(
    (run) => isTerminal(run.status),
  );

  async function exportReport(
    run: (typeof completedRuns)[number],
  ) {
    setExportError("");
    setExporting(run.id);

    try {
      const events = await getExperimentEvents(run.id);

      const evidence = {
        schema_version: "opsproof-evidence/v1",
        exported_at: new Date().toISOString(),
        source: "local-control-plane",
        experiment: run,
        events,
      };

      const blob = new Blob(
        [JSON.stringify(evidence, null, 2)],
        { type: "application/json" },
      );

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `opsproof-${shortId(run.id)}.json`;

      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(url);
    } catch {
      setExportError(
        "Could not export the evidence. Retry after checking the API.",
      );
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">EVIDENCE ARCHIVE</p>
          <h1>Every result has a record.</h1>

          <p className="page-description">
            Inspect completed experiments and preserve
            their recorded outcomes.
          </p>
        </div>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Completed experiment records</h2>
            <p>
              Terminal experiments among the latest 50 records
            </p>
          </div>

          <button
            className="icon-button"
            type="button"
            aria-label="Refresh reports"
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={17} />
          </button>
        </div>

        {exportError && (
          <p className="inline-error" role="alert">
            {exportError}
          </p>
        )}

        {query.isPending && (
          <p className="state-message" role="status">
            Loading evidence records...
          </p>
        )}

        {query.isError && (
          <div className="error-panel" role="alert">
            Could not load report history.
          </div>
        )}

        {query.isSuccess && completedRuns.length === 0 && (
          <div className="empty-state">
            <FileJson2 size={26} />

            <h3>No completed reports yet</h3>

            <p>
              Once an experiment reaches a terminal state,
              its recorded result will be available here.
            </p>
          </div>
        )}

        {completedRuns.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Experiment</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Completed</th>
                  <th scope="col">Evidence</th>
                </tr>
              </thead>

              <tbody>
                {completedRuns.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link
                        className="table-primary table-link"
                        to={`/experiments/${run.id}`}
                      >
                        {run.scenario}
                      </Link>

                      <span className="table-secondary mono">
                        {shortId(run.id)}
                      </span>
                    </td>

                    <td>
                      <RunStatus status={run.status} />
                    </td>

                    <td className="muted">
                      {formatDate(run.completed_at)}
                    </td>

                    <td>
                      <button
                        className="button button--small button--secondary"
                        type="button"
                        onClick={() => void exportReport(run)}
                        disabled={exporting === run.id}
                      >
                        <Download size={15} />
                        {exporting === run.id
                          ? "Exporting..."
                          : "Export JSON"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
