import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { approveKubernetesRecovery, getKubernetesRecoveries, getKubernetesWorkloads, proposeKubernetesRecovery } from "../lib/api";
import { formatDate } from "../lib/format";

export function KubernetesPage({ view }: { view: "Workloads" | "Deployments" | "Capacity" | "Runbooks" }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5000);
    return () => window.clearInterval(timer);
  }, []);
  const workload = useQuery({ queryKey: ["kubernetes-workloads"], queryFn: getKubernetesWorkloads, refetchInterval: 5000 });
  const recoveries = useQuery({ queryKey: ["kubernetes-recoveries"], queryFn: getKubernetesRecoveries, enabled: workload.data?.enabled === true && view === "Runbooks", refetchInterval: 5000 });
  const [incident, setIncident] = useState("");
  const [run, setRun] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function act(operation: () => Promise<unknown>) {
    setBusy(true); setMessage("");
    try { await operation(); await recoveries.refetch(); setMessage("Request recorded. Follow its independently verified outcome below."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Request failed"); }
    finally { setBusy(false); }
  }
  return <section className="page">
    <header className="page-header"><div><p className="eyebrow">LOCAL KUBERNETES</p><h1>{view}</h1><p className="muted">Observed state of the supported demo worker. Observations refresh every five seconds.</p></div></header>
    {workload.isPending && <p role="status">Loading workload observations…</p>}
    {workload.isError && <p role="alert">Workload observations are unavailable.</p>}
    {workload.data && !workload.data.enabled && <p role="status">Kubernetes recovery and observation are disabled in this environment.</p>}
    {workload.data?.enabled && workload.data.observations.length === 0 && <p role="status">Waiting for the first independent observation.</p>}
    {workload.data?.observations.map(observation => {
      const resource = observation.resource;
      const container = resource.spec.template.spec.containers[0];
      const fresh = now - Date.parse(observation.observed_at) <= 15000;
      return <article className="panel" key={observation.name}>
        <h2>{resource.metadata.name}</h2><p>{resource.metadata.namespace}</p>
        <p role="status">{fresh ? "Recent observation" : "Stale observation — current health is unknown"} · {formatDate(observation.observed_at)}</p>
        {view === "Workloads" && <dl><dt>Requested replicas</dt><dd>{resource.spec.replicas}</dd><dt>Ready replicas</dt><dd>{resource.status.readyReplicas ?? 0}</dd><dt>Service dependencies</dt><dd>{fresh && observation.telemetry.ready ? "Ready" : "Not established"}</dd></dl>}
        {view === "Deployments" && <dl><dt>Observed image</dt><dd style={{ overflowWrap: "anywhere" }}>{container.image}</dd><dt>Workload identity</dt><dd>{resource.metadata.uid}</dd><dt>Observed resource version</dt><dd>{resource.metadata.resourceVersion}</dd></dl>}
        {view === "Capacity" && <><dl><dt>Queued jobs at last scrape</dt><dd>{observation.telemetry.queued}</dd><dt>CPU reserved per worker</dt><dd>{container.resources.requests.cpu}</dd><dt>Memory reserved per worker</dt><dd>{container.resources.requests.memory}</dd><dt>CPU / memory limits</dt><dd>{container.resources.limits.cpu} / {container.resources.limits.memory}</dd></dl><p className="muted">Reservations are configured capacity, not measured consumption. Cloud billing is not configured for this local environment; no cost estimate is available.</p></>}
      </article>;
    })}
    {view === "Runbooks" && workload.data?.enabled && <>
      <article className="panel"><h2>Restore one stopped demo worker</h2><p>This operation starts exactly one worker in opsproof-demo. It requires a firing queue incident, a linked experiment, recent telemetry and a stopped worker. KEDA must be disabled. Approval expires after two minutes.</p>
        <form onSubmit={event => { event.preventDefault(); void act(() => proposeKubernetesRecovery(incident, run)); }}>
          <label htmlFor="k8s-incident">Incident fingerprint</label><input id="k8s-incident" value={incident} onChange={e => setIncident(e.target.value)} required />
          <label htmlFor="k8s-run">Experiment ID</label><input id="k8s-run" value={run} onChange={e => setRun(e.target.value)} required />
          <button className="button button--secondary" disabled={busy} type="submit">Review recovery proposal</button>
        </form>
      </article>
      {message && <p role="status">{message}</p>}
      {recoveries.isError && <p role="alert">Recovery records are unavailable.</p>}
      {recoveries.data?.map(recovery => <article className="panel" key={recovery.id}><h2>Worker restoration</h2><p>{recovery.status}</p><p>Proposed {formatDate(recovery.created_at)} · Expires {formatDate(recovery.expires_at)}</p><p style={{ overflowWrap: "anywhere" }}>Image: {recovery.target_image}</p><p>Target identity: {recovery.target_uid}</p>{recovery.error && <p>{recovery.error}</p>}{recovery.status === "pending_approval" && <button className="button button--primary" disabled={busy || Date.parse(recovery.expires_at) <= now} onClick={() => void act(() => approveKubernetesRecovery(recovery.id))}>Approve restoring one demo worker</button>}</article>)}
    </>}
  </section>;
}
