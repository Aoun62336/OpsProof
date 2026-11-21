"""Run inside the final Python artifact; never import mounted application source.

Input is supplied by validate_python_image over stdin. Only disposable loopback
PostgreSQL/Redis and an in-process OTLP receiver are reachable in its namespace.
"""

import bz2
import http.cookiejar
import importlib.util
import json
import lzma
import os
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import redis
from psycopg import sql
from psycopg.rows import dict_row


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def serve_capture():
    # Owned loopback fixture: records only span identities, never payloads/credentials.
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    spans = []
    jobs = {}

    class Capture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/captured":
                self.reply(spans)
            elif self.path == "/health/ready":
                self.reply({"status": "ready"})
            elif self.path == "/api/v1/stats":
                self.reply({"queued": 0, "processing": 0, "completed": len(jobs), "failed": 0})
            elif self.path.startswith("/api/v1/jobs/"):
                self.reply(jobs.get(self.path.rsplit("/", 1)[-1], {}))
            else:
                self.reply({}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 2_000_000:
                self.reply({}, 413)
                return
            payload = self.rfile.read(length)
            if self.path == "/v1/traces":
                request = ExportTraceServiceRequest.FromString(payload)
                for resource in request.resource_spans:
                    service = next(
                        (
                            a.value.string_value
                            for a in resource.resource.attributes
                            if a.key == "service.name"
                        ),
                        "",
                    )
                    for scope in resource.scope_spans:
                        for span in scope.spans:
                            spans.append(
                                {
                                    "name": span.name,
                                    "trace_id": span.trace_id.hex(),
                                    "service": service,
                                    "parent": span.parent_span_id.hex(),
                                }
                            )
                del spans[:-256]
            elif self.path == "/api/v1/jobs":
                # Control-only boundary fixture; not claimed as actual demo execution.
                key = self.headers.get("Idempotency-Key", "")
                existing = next((j for j in jobs.values() if j["key"] == key), None)
                if existing is None:
                    identifier = str(uuid4())
                    existing = {"id": identifier, "status": "completed", "key": key}
                    jobs[identifier] = existing
                self.reply(existing, 202)
                return
            self.reply({})

    HTTPServer(("127.0.0.1", 4318), Capture).serve_forever()


def prepare_control():
    from opsproof_control.database_permissions import grant_application_tables

    with psycopg.connect(os.environ["OPSPROOF_CONTROL_DATABASE_URL"], row_factory=dict_row) as conn:
        conn.execute(
            sql.SQL(
                "CREATE ROLE opsproof_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Literal(os.environ["IMAGE_TEST_APP_PASSWORD"]))
        )
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO opsproof_app").format(
                sql.Identifier(conn.info.dbname)
            )
        )
        conn.execute("GRANT USAGE ON SCHEMA public TO opsproof_app")
        grant_application_tables(conn, "opsproof_app")
    return {"restricted_application_role_created": True}


def telemetry_check():
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(
            OTLPSpanExporter(endpoint=f"http://127.0.0.1:{server.server_port}/v1/traces", timeout=3)
        )
    )
    try:
        with provider.get_tracer("image-validation").start_as_current_span("image-validation"):
            pass
        check(bool(received), "OTLP HTTP exporter did not transmit a span")
        request = ExportTraceServiceRequest.FromString(received[0])
        check(
            request.resource_spans[0].scope_spans[0].spans[0].name == "image-validation",
            "OTLP protobuf payload differs from the actual span",
        )
    finally:
        provider.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def probe():
    component = os.environ["IMAGE_TEST_COMPONENT"]
    prefix = "OPSPROOF_CONTROL_" if component == "control" else "OPSPROOF_"
    package = "opsproof_control" if component == "control" else "opsproof_demo"
    spec = importlib.util.find_spec(package)
    check(spec and "/app/.venv/" in spec.origin, "Application did not load from the final artifact")
    check(os.getuid() == 10001, "Application lost its nonroot identity")
    check(sys.version_info[:3] == (3, 14, 10), "Unexpected Python version")
    check(importlib.util.find_spec("pip") is None, "Unused runtime installer is present")
    try:
        with open("/app/unexpected-write", "w"):
            pass
    except OSError as error:
        check(error.errno == 30, "Filesystem denial was not read-only enforcement")
    else:
        raise AssertionError("Application root is writable")
    check(bz2.decompress(bz2.compress(b"check")) == b"check", "bz2 extension failed")
    check(lzma.decompress(lzma.compress(b"check")) == b"check", "lzma extension failed")
    check(ZoneInfo("Asia/Kolkata") is not None, "Timezone data is unavailable")
    check(
        sqlite3.sqlite_version_info >= (3, 54, 0),
        "SQLite predates the upstream fixes for the original three CVEs",
    )
    check(bool(ssl.create_default_context().get_ca_certs()), "System CA trust is unavailable")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE VIRTUAL TABLE example USING fts5(content)")
        conn.execute("INSERT INTO example VALUES ('operational evidence')")
        check(
            conn.execute(
                "SELECT count(*) FROM example WHERE example MATCH 'operational'"
            ).fetchone()[0]
            == 1,
            "SQLite/FTS5 standard-library functionality was lost",
        )
    with psycopg.connect(os.environ[prefix + "DATABASE_URL"], row_factory=dict_row) as conn:
        check(
            conn.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone()["ssl"]
            is True,
            "PostgreSQL connection is not TLS",
        )
        if component == "control":
            from opsproof_control.trial_access import require_application_role

            require_application_role(conn)
    for overrides in (
        {"sslrootcert": "/tls/wrong.crt"},
        {"host": "wrong.invalid", "hostaddr": "127.0.0.1"},
    ):
        try:
            with psycopg.connect(
                os.environ[prefix + "DATABASE_URL"], connect_timeout=3, **overrides
            ):
                pass
        except psycopg.OperationalError as error:
            check(
                "certificate" in str(error).lower(), "TLS negative case failed for another reason"
            )
        else:
            raise AssertionError("PostgreSQL accepted an untrusted CA/hostname")
    client = redis.Redis.from_url(os.environ[prefix + "REDIS_URL"], socket_timeout=3)
    try:
        check(client.ping(), "Redis TLS/auth connection failed")
        for overrides, kind in (
            ({"password": "wrong-test-password"}, redis.AuthenticationError),
            ({"ssl_ca_certs": "/tls/wrong.crt"}, redis.ConnectionError),
        ):
            invalid_pool = redis.ConnectionPool(
                connection_class=client.connection_pool.connection_class,
                **{**client.connection_pool.connection_kwargs, **overrides},
            )
            invalid = redis.Redis(connection_pool=invalid_pool)
            try:
                invalid.ping()
            except kind:
                pass
            else:
                raise AssertionError("Redis accepted invalid authentication/TLS trust")
            finally:
                invalid.close()
                invalid_pool.disconnect()
    finally:
        client.close()
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies)
    )

    def request(path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8080" + path,
            data=data,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        with opener.open(req, timeout=5) as response:
            return response.status, json.loads(response.read())

    check(request("/health/ready")[0] == 200, "API dependencies are not ready")
    trace_id = uuid4().hex
    trace_headers = {"traceparent": f"00-{trace_id}-{uuid4().hex[:16]}-01"}
    if component == "demo":
        key = "image-check-" + uuid4().hex
        body = {"duration_ms": 50}
        code, first = request("/api/v1/jobs", body, {"Idempotency-Key": key, **trace_headers})
        check(code == 202, "Job admission failed")
        _, second = request("/api/v1/jobs", body, {"Idempotency-Key": key})
        check(first["id"] == second["id"], "Job idempotency failed")
        deadline = time.monotonic() + 25
        while True:
            _, job = request("/api/v1/jobs/" + first["id"])
            if job["status"] == "completed":
                break
            check(time.monotonic() < deadline, "Actual dispatcher/worker did not complete the job")
            time.sleep(0.2)
        check(job["attempts"] == 1, "Ordinary processing unexpectedly retried")
    else:
        try:
            request("/api/v1/m6/trials")
        except urllib.error.HTTPError as error:
            check(error.code == 401, "Unauthenticated request was not rejected")
        else:
            raise AssertionError("Unauthenticated trial read succeeded")
        check(
            request("/api/v1/auth/login", {"access_key": os.environ[prefix + "API_KEY"]})[0] == 200,
            "Actual SQL-backed browser login failed",
        )
        check(request("/api/v1/m6/trials")[0] == 200, "Authenticated ledger read failed")
        code, run = request(
            "/api/v1/experiments",
            {"scenario": "queue-burst", "count": 1, "duration_ms": 50},
            {
                "X-OpsProof-Key": os.environ[prefix + "API_KEY"],
                "Idempotency-Key": "image-experiment-" + uuid4().hex,
                **trace_headers,
            },
        )
        check(code == 202, "Actual experiment admission failed")
        deadline = time.monotonic() + 30
        while True:
            _, finished = request(
                "/api/v1/experiments/" + run["id"],
                headers={"X-OpsProof-Key": os.environ[prefix + "API_KEY"]},
            )
            if finished["status"] == "succeeded":
                break
            check(finished["status"] != "failed", "Control experiment failed")
            check(
                time.monotonic() < deadline, "Control dispatcher/action/evidence did not complete"
            )
            time.sleep(0.2)
    deadline = time.monotonic() + 20
    required = (
        {"opsproof-demo-api", "opsproof-demo-dispatcher", "opsproof-demo-worker"}
        if component == "demo"
        else {
            "opsproof-control-api",
            "opsproof-control-dispatch",
            "opsproof-control-action",
            "opsproof-control-evidence",
        }
    )
    while True:
        with urllib.request.urlopen("http://127.0.0.1:4318/captured", timeout=3) as response:
            spans = json.load(response)
        observed = {s["service"] for s in spans if s["trace_id"] == trace_id}
        if required <= observed:
            break
        check(
            time.monotonic() < deadline,
            "Actual asynchronous trace context did not reach every role",
        )
        time.sleep(0.5)
    telemetry_check()
    return {
        "component": component,
        "python": sys.version.split()[0],
        "uid": os.getuid(),
        "sqlite": sqlite3.sqlite_version,
        "openssl": ssl.OPENSSL_VERSION,
        "installed_application": True,
        "read_only": True,
        "postgres_tls_and_negatives": True,
        "redis_tls_auth_and_negatives": True,
        "api_and_workers": True,
        "stdlib_extensions": True,
        "otlp_http_protobuf": True,
        "asynchronous_trace_context": True,
        "control_target_is_fixture": component == "control",
    }


if __name__ == "__main__":
    if os.environ["IMAGE_TEST_STAGE"] == "receiver":
        serve_capture()
    result = prepare_control() if os.environ["IMAGE_TEST_STAGE"] == "prepare" else probe()
    print(json.dumps(result))
