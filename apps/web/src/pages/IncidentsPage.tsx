import {
  useState,
} from "react";

import {
  useQuery,
} from "@tanstack/react-query";

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import {
  getIncidents,
  getIncidentEvents,
} from "../lib/api";

import {
  formatDate,
  titleCase,
} from "../lib/format";

import type {
  Incident,
  IncidentStatus,
} from "../lib/types";


type Filter = "all" | IncidentStatus;


export function IncidentsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(
    null,
  );

  const incidents = useQuery({
    queryKey: ["incidents", filter],

    queryFn: () =>
      getIncidents(
        filter === "all" ? undefined : filter,
      ),

    refetchInterval: 10_000,
    retry: 1,
  });

  const events = useQuery({
    queryKey: ["incident-events", selected],

    queryFn: () =>
      getIncidentEvents(selected ?? ""),

    enabled: Boolean(selected),
    retry: 1,
  });

  const records = incidents.isError
    ? []
    : incidents.data ?? [];

  const active = records.filter(
    (incident) => incident.status === "firing",
  ).length;

  return (
    <div className="page incidents-page">
      <header className="page-header">
        <div>
          <p className="overline">
            INCIDENT INTELLIGENCE / LOCAL
          </p>

          <h1>Incidents</h1>

          <p className="page-description">
            Detected conditions, alert lifecycles
            and recorded evidence.
          </p>
        </div>

        <button
          className="button button--secondary"
          type="button"
          onClick={() => void incidents.refetch()}
        >
          <RefreshCw
            size={16}
            aria-hidden="true"
          />
          Refresh
        </button>
      </header>

      <div className="incident-intro">
        <div>
          <p className="overline overline--light">
            ALERTMANAGER / PROMETHEUS
          </p>

          <h2>
            Detection is not the same as recovery.
          </h2>

          <p>
            Incident status reflects monitoring-rule
            transitions. Actual workload recovery must
            be verified separately.
          </p>
        </div>

        <ShieldAlert
          size={30}
          aria-hidden="true"
        />
      </div>

      <section
        className="panel"
        aria-labelledby="incident-list-heading"
      >
        <div className="panel-header">
          <div>
            <p className="overline">
              RECORDED INCIDENTS
            </p>

            <h2 id="incident-list-heading">
              Alert history
            </h2>

            <p>
              Latest 50 matching records
            </p>
          </div>

          <div className="incident-filter">
            <label htmlFor="incident-filter">
              Status
            </label>

            <select
              id="incident-filter"
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value as Filter);
                setSelected(null);
              }}
            >
              <option value="all">All</option>
              <option value="firing">Firing</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
        </div>

        {incidents.isPending && (
          <p className="state-message" role="status">
            Loading incident records…
          </p>
        )}

        {incidents.isError && (
          <div className="error-panel" role="alert">
            Incident records are unavailable.
            This does not mean there are no incidents.
          </div>
        )}

        {incidents.isSuccess &&
          records.length === 0 && (
            <div className="empty-state">
              <ShieldAlert
                size={24}
                aria-hidden="true"
              />

              <strong>No matching alert records</strong>

              <p>
                This does not establish that every
                workload or monitoring integration
                is healthy.
              </p>
            </div>
          )}

        {incidents.isSuccess &&
          records.length > 0 && (
            <div className="incident-list">
              {records.map((incident) => (
                <IncidentRow
                  key={incident.fingerprint}
                  incident={incident}
                  selected={
                    selected === incident.fingerprint
                  }
                  onSelect={() =>
                    setSelected(
                      selected === incident.fingerprint
                        ? null
                        : incident.fingerprint,
                    )
                  }
                />
              ))}
            </div>
          )}

        {incidents.isSuccess && (
          <p className="incident-footnote">
            {filter === "all"
              ? `${active} firing alert records among the displayed records.`
              : `Filtered to ${filter} alerts.`}
          </p>
        )}
      </section>

      {selected && (
        <section
          className="panel incident-timeline-panel"
          aria-labelledby="incident-events-heading"
        >
          <div className="panel-header">
            <div>
              <p className="overline">
                AUDIT TIMELINE
              </p>

              <h2 id="incident-events-heading">
                Recorded state transitions
              </h2>
            </div>
          </div>

          {events.isPending && (
            <p className="state-message" role="status">
              Loading transitions…
            </p>
          )}

          {events.isError && (
            <p className="inline-error" role="alert">
              Could not retrieve this incident's history.
            </p>
          )}

          {events.data && (
            <ol className="incident-event-list">
              {events.data.map((event) => (
                <li key={event.id}>
                  <strong>
                    {titleCase(event.status)}
                  </strong>

                  <time dateTime={event.created_at}>
                    {formatDate(event.created_at)}
                  </time>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      <p className="scope-note">
        OpsProof currently detects local Prometheus
        alert conditions. Kubernetes incident correlation
        and automated remediation are separate,
        controlled capabilities.
      </p>
    </div>
  );
}


function IncidentRow({
  incident,
  selected,
  onSelect,
}: {
  incident: Incident;
  selected: boolean;
  onSelect: () => void;
}) {
  const active = incident.status === "firing";
  const critical = incident.severity === "critical";

  const Icon = active
    ? AlertTriangle
    : CheckCircle2;

  return (
    <div className="incident-row">
      <div className="incident-row__icon">
        <Icon
          size={20}
          aria-hidden="true"
        />
      </div>

      <div className="incident-row__content">
        <div className="incident-row__heading">
          <strong>{incident.name}</strong>

          <span
            className={
              active
                ? critical
                  ? "incident-state incident-state--critical"
                  : "incident-state incident-state--warning"
                : "incident-state incident-state--resolved"
            }
          >
            {active ? "Firing" : "Resolved"}
          </span>
        </div>

        <p>{incident.summary}</p>

        <small>
          {incident.target} ·{" "}
          {formatDate(incident.started_at)}
        </small>
      </div>

      <button
        className="incident-row__action"
        type="button"
        aria-expanded={selected}
        onClick={onSelect}
      >
        History
        <ArrowRight
          size={15}
          aria-hidden="true"
        />
      </button>
    </div>
  );
}
