"""Read-only durable identity, metrics, log and trace evidence collectors."""

import math
import time
from datetime import datetime
from urllib.parse import urlencode
from uuid import UUID

from scripts.m6.local_environment import http


def sql(env, query):
    import psycopg

    from scripts.m6.restricted_access import observer_dsn

    with psycopg.connect(observer_dsn(), connect_timeout=2) as conn:
        conn.execute("SET LOCAL statement_timeout='2s'")
        conn.execute("SET LOCAL transaction_read_only=on")
        return conn.execute(query).fetchone()[0]


def durable_jobs(env, ids):
    if not ids:
        return []
    if len(ids) > 120 or len(set(ids)) != len(ids):
        raise ValueError("Duplicate or excessive durable job IDs")
    identities = ",".join("'" + str(UUID(value)) + "'::uuid" for value in ids)
    return sql(
        env,
        "SELECT coalesce(json_agg(row_to_json(j)),'[]'::json) FROM ("
        "SELECT id,idempotency_key,status,duration_ms,attempts,"
        "created_at,started_at,completed_at FROM jobs "
        f"WHERE id IN ({identities}) ORDER BY id) j",
    )


def durable_inventory(env, cutoff):
    timestamp = datetime.fromisoformat(cutoff)
    if timestamp.tzinfo is None:
        raise ValueError("Timezone-aware inventory cutoff required")
    return sql(
        env,
        "SELECT json_build_object('count',count(*),'id_fingerprint',"
        "md5(coalesce(string_agg(id::text||':'||status||':'||attempts::text||':'||"
        "coalesce(completed_at::text,''),',' ORDER BY id),''))) FROM jobs "
        f"WHERE created_at<='{timestamp.isoformat()}'::timestamptz",
    )


def reconcile_submission_keys(env, state):
    """Resolve lost response IDs by exact durable keys, without resubmitting."""
    import re

    keys = state["submitted_keys"]
    if (
        len(keys) > 120
        or len(set(keys)) != len(keys)
        or any(
            not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", key)
            for key in keys
        )
    ):
        raise ValueError("Invalid or duplicate saved submission keys")
    if not keys:
        return
    quoted = ",".join("'" + key + "'" for key in keys)
    rows = sql(
        env,
        "SELECT coalesce(json_agg(row_to_json(j)),'[]'::json) FROM "
        f"(SELECT id,idempotency_key FROM jobs WHERE idempotency_key IN ({quoted})) j",
    )
    actual = {row["idempotency_key"]: row["id"] for row in rows}
    if set(actual) != set(keys) or len(rows) != len(keys):
        raise ValueError(
            "A saved submission intent remains unknown; no replay or reservation release"
        )
    if not set(state["job_ids"]).issubset(actual.values()):
        raise ValueError("Saved job IDs do not match the durable submission keys")
    state["job_ids"] = [actual[key] for key in keys]


def prometheus(env):
    raw = {}
    for name, query in {
        "up": 'up{job="opsproof-demo-api"}',
        "sample_time": 'timestamp(up{job="opsproof-demo-api"})',
        "queue": 'opsproof_demo_jobs{job="opsproof-demo-api"}',
    }.items():
        status, result = http(19090, "/api/v1/query?" + urlencode({"query": query}))
        if status != 200 or not result or result.get("status") != "success":
            raise ValueError("Current Prometheus query unavailable")
        raw[name] = result
    values = []
    for name in ("up", "sample_time"):
        items = raw[name]["data"]["result"]
        if len(items) != 1:
            raise ValueError("Prometheus sample is missing or ambiguous")
        values.append(float(items[0]["value"][1]))
    fresh = (
        all(math.isfinite(v) for v in values)
        and values[0] == 1
        and 0 <= time.time() - values[1] <= 30
    )
    env.save("prometheus-current", raw)
    return {"fresh": fresh, "sample_time": values[1], "up": values[0]}


def spans(trace):
    return [
        (batch.get("resource", {}), span)
        for batch in trace.get("batches", trace.get("resourceSpans", []))
        for scope in batch.get("scopeSpans", [])
        for span in scope.get("spans", [])
    ]


def telemetry(env, state):
    start = datetime.fromisoformat(state["injection_started_at"]).timestamp()
    query = '{service_name="opsproof-demo-worker"}'
    if state["scenario"] == "database_connectivity":
        query = '{service_name=~"opsproof-demo-(api|worker)"}'
    status, logs = http(
        13100,
        "/loki/api/v1/query_range?"
        + urlencode(
            {
                "query": query,
                "start": str(int(start * 1e9)),
                "end": str(time.time_ns()),
                "limit": 200,
            }
        ),
    )
    log_values = [
        value[1]
        for stream in (logs or {}).get("data", {}).get("result", [])
        for value in stream.get("values", [])
    ]
    env.save("loki-current-window", {"status": status, "query": query, "response": logs})
    if state["job_ids"]:
        log_match = any(any(job in line for job in state["job_ids"]) for line in log_values)
    else:
        log_match = bool(log_values)
    traces = []
    if state["scenario"] == "downstream_latency" and state["job_ids"]:
        # Search only actual job-linked worker spans; never use a generic probe
        # as a substitute for the required delayed HTTP client/server trace.
        job = str(UUID(state["job_ids"][0]))
        query = (
            '{ resource.service.name="opsproof-demo-worker" && span.opsproof.job.id="' + job + '" }'
        )
        code, search = http(
            13200,
            "/api/search?"
            + urlencode(
                {
                    "q": query,
                    "start": int(start),
                    "end": int(time.time()),
                    "limit": 10,
                }
            ),
        )
        env.save("tempo-job-search", {"status": code, "response": search})
        ids = [item["traceID"] for item in (search or {}).get("traces", [])]
    else:
        ids = state.get("failed_trace_ids", [])[:5]
    for identity in ids:
        if not identity or any(c not in "0123456789abcdefABCDEF" for c in identity):
            raise ValueError("Invalid observed Tempo trace identity")
        code, trace = http(13200, "/api/traces/" + identity)
        if code != 200 or not trace:
            continue
        env.save("tempo-trace", {"trace_id": identity, "response": trace})
        entries = spans(trace)
        names = {span.get("name") for _, span in entries}
        services = {
            a.get("value", {}).get("stringValue")
            for resource, _ in entries
            for a in resource.get("attributes", [])
            if a.get("key") == "service.name"
        }
        clients = [span for _, span in entries if span.get("name") == "opsproof.downstream"]
        server_parents = {
            span.get("parentSpanId")
            for _, span in entries
            if span.get("kind") in (2, "SPAN_KIND_SERVER")
        }
        linked = any(client.get("spanId") in server_parents for client in clients)
        timed_out = any(
            span.get("status", {}).get("code") in (2, "STATUS_CODE_ERROR")
            and span.get("kind") in (3, "SPAN_KIND_CLIENT")
            for span in clients
        )
        traces.append(
            {
                "id": identity,
                "span_count": len(entries),
                "names": sorted(n for n in names if n),
                "services": sorted(s for s in services if s),
                "linked_client_server": linked,
                "timeout_error": timed_out,
            }
        )
    return {
        "logs_relevant": log_match,
        "log_lines": len(log_values),
        "traces": traces,
        "downstream_linked": any(t["linked_client_server"] for t in traces),
        "downstream_timeout": any(t["timeout_error"] for t in traces),
    }
