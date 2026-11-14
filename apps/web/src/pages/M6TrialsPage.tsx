import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, getM6TrialArtifacts, getM6TrialEvents, getM6Trials, getM6Verifications } from "../lib/api";
import { formatDate } from "../lib/format";

export function M6TrialsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const trials = useQuery({
    queryKey: ["m6", "trials"], queryFn: getM6Trials, retry: false,
    refetchInterval: 20_000,
  });
  const events = useQuery({
    queryKey: ["m6", "events", selected],
    queryFn: () => getM6TrialEvents(selected!),
    enabled: selected !== null,
    retry: false,
  });
  const disabled = trials.error instanceof ApiError && trials.error.status === 404
    && trials.error.message === "M6 ledger is disabled";
  const artifacts = useQuery({
    queryKey: ["m6", "artifacts", selected],
    queryFn: () => getM6TrialArtifacts(selected!),
    enabled: selected !== null,
    retry: false,
  });
  const selectedTrial = trials.data?.find((trial) => trial.id === selected);
  const verifications = useQuery({
    queryKey: ["m6", "verifications", selected],
    queryFn: () => getM6Verifications(selected!),
    enabled: selected !== null,
    retry: false,
  });

  return (
    <div className="page m6-trials">
      <header className="page-header">
        <div>
          <p className="overline">RELIABILITY VERIFICATION</p>
          <h1>M6 trial ledger</h1>
          <p className="page-description">
            Read-only records. A recorded trial is not independently verified until
            its evidence and cleanup gates are satisfied.
          </p>
        </div>
      </header>
      {disabled ? (
        <section className="panel" role="status">
          <h2>Trial ledger is disabled</h2>
          <p>The M6 service is opt-in. Your accepted M5 operations remain unaffected.</p>
        </section>
      ) : trials.isLoading ? (
        <p role="status">Loading trial records...</p>
      ) : trials.isError ? (
        <p role="alert">Unable to load trials. Check API availability and access.</p>
      ) : (
        <section className="panel" aria-label="M6 trials">
          <h2>Recorded trials</h2>
          {trials.data?.length === 0 ? (
            <p>No M6 trials have been recorded.</p>
          ) : (
            <ul>
              {trials.data?.map((trial) => (
                <li key={trial.id}>
                  <button type="button" className="button button--secondary"
                    aria-pressed={selected === trial.id}
                    onClick={() => setSelected(trial.id)}>
                    {trial.scenario.replaceAll("_", " ")}
                  </button>{" "}
                  <strong>{trial.phase}</strong>{" "}
                  <time dateTime={trial.created_at}>{formatDate(trial.created_at)}</time>
                  <p>Target: <code>{trial.target}</code></p>
                  <p>Trial ID: <code>{trial.id}</code></p>
                  <p>Submitted source revision: <code>{trial.source_revision}</code></p>
                  {trial.error && <p className="inline-error">{trial.error}</p>}
                  <p>Independent proof: {trial.independent_verified ? "Recorded" : "Not established"}
                    {" | "}Cleanup: {trial.cleanup_verified ? "Recorded" : "Not established"}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {selected && (
        <section className="panel" aria-label="Trial events">
          <h2>Audit timeline</h2>
          {selectedTrial && <p>Trial <code>{selectedTrial.id}</code> · {selectedTrial.phase}</p>}
          {events.isLoading && <p role="status">Loading recorded events...</p>}
          {events.isError && <p role="alert">Could not read event history.</p>}
          {events.data?.length === 0 && <p>No events are available.</p>}
          <ol>
            {events.data?.map((event) => (
              <li key={event.id}>
                <time dateTime={event.created_at}>{formatDate(event.created_at)}</time>
                {" · "}{event.kind}
                {Object.keys(event.details).length > 0 && (
                  <details><summary>Recorded details</summary>
                    <pre>{JSON.stringify(event.details, null, 2)}</pre>
                  </details>
                )}
              </li>
            ))}
          </ol>
          <h3>Evidence references</h3>
          {artifacts.isLoading && <p role="status">Loading evidence references...</p>}
          {artifacts.isError && <p role="alert">Could not read evidence references.</p>}
          {artifacts.data?.length === 0 && <p>No evidence has been attached.</p>}
          <ul>{artifacts.data?.map((artifact) => (
            <li key={artifact.id}>
              <strong>{artifact.kind}</strong>: <code>{artifact.relative_path}</code>
              <p>SHA-256: <code>{artifact.sha256}</code></p>
              {artifact.observations && Object.keys(artifact.observations).length > 0 && (
                <details><summary>Observed data</summary>
                  <pre>{JSON.stringify(artifact.observations, null, 2)}</pre>
                </details>
              )}
            </li>
          ))}</ul>
          <h3>Independent verification</h3>
          {verifications.isLoading && <p role="status">Loading verification records...</p>}
          {verifications.isError && <p role="alert">Could not read independent verification.</p>}
          {verifications.data?.length === 0 && <p>No independent verification has been recorded.</p>}
          {verifications.data?.map((proof) => (
            <article key={proof.observer_id}>
              <p><time dateTime={proof.verified_at}>{formatDate(proof.verified_at)}</time></p>
              <p>Fault hypothesis: {proof.hypothesis_verified ? "Established" : "Not established"}
                {" | "}Cleanup: {proof.cleanup_verified ? "Verified" : "Not established"}</p>
              <p>Dispatch: <code>{proof.dispatch_id}</code></p>
              <p>Report SHA-256: <code>{proof.report_sha256}</code></p>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
