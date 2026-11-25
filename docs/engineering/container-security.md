# Container security and release gate

Verified locally on 21 November 2026. All four final images passed complete
vulnerability scans with zero CRITICAL, HIGH, MEDIUM, LOW or UNKNOWN findings.
This is a dated result, not a guarantee against future vulnerabilities. Hosted
CI, image publication and cloud acceptance remain separate owner gates.

## Python runtime remediation

The previous Debian trixie images had 47 HIGH package/advisory occurrences per
image, representing eleven distinct CVEs. No HIGH/CRITICAL package fixes were
available in the original scan. Both Python Dockerfiles now use the free public
[Wolfi base](https://images.chainguard.dev/directory/image/wolfi-base/overview),
pinned to `sha256:be019c1c74fe69204a42c4e10bc4d886a49bf5403ffa74374ef7baa408fc9a26`.
Signed vendor packages supply:

- [`python-3.14=3.14.10_git20261118-r0`](https://github.com/wolfi-dev/os/blob/main/python-3.14.yaml):
  the existing Python 3.14.10 version with vendor security patches.
- [`sqlite-libs=3.54.1-r1`](https://github.com/wolfi-dev/os/blob/main/sqlite.yaml):
  newer than the upstream 3.54.0 security-fix floor.
- The vendor's glibc runtime libraries, system trust store and timezone data.

The runtime-only remediation preserved application source, lockfiles and
migrations. The subsequent observability change adds compatible outbox-context
migrations and metrics; the Python lockfiles remain unchanged. The glibc
runtime retains compatibility with the locked native wheels. Unused Debian
packages are not carried into the replacement distribution. Package metadata
remains intact for scanning. No forced dependency removal, unstable repository,
custom-compiled library, CVE suppression or security exception is used.

| Verification | Actual result |
|---|---|
| Complete Python image scans | Zero findings in both images |
| Original eleven HIGH advisories | Absent at every severity in both new reports |
| Python and SQLite inside both artifacts | Python 3.14.10; SQLite 3.54.1 |
| PostgreSQL and Redis | Real TLS/auth connections and wrong-CA/hostname/password rejection passed |
| Demo API, dispatcher and worker | Idempotent job admission and actual job completion passed |
| Control API and four background roles | Restricted database-role access, browser login and authenticated ledger read passed; all roles stayed running |
| Standard library and telemetry | CA trust, timezones, compression, SQLite FTS5 and OTLP HTTP/protobuf export passed |
| Runtime restrictions and shutdown | UID 10001, read-only root, no pip import; all eight roles exited zero on SIGTERM |

An Alpine prototype was rejected: its SQLite 3.53.4 was below the upstream fixed
version despite the scanner not reporting those SQLite advisories. The final
artifact check therefore requires SQLite >= 3.54.0 independently of the scanner.
See the [upstream SQLite release](https://sqlite.org/releaselog/3_54_0.html).

The exact locally scanned image identities are:

```text
demo     sha256:18fb10dee7ab76d66b7e4c37224033eb3d9ee76367b94dd607384ceee95f2b66
control  sha256:35916610c6ec37e46c927a5ef0b6f45015df4947e61592ae6aeda68f1ee781f8
web      sha256:f9a261c1b986c43df3a44c42355cfaff5345389458f1786189c49c23f4b0c51d
edge     sha256:cc7f1af5a2143bcc3c1d493a031eb27c82afe52d4f0275535d8d9a5b2638a353
```

Hash-verified image exports, full Trivy 0.76.2 reports, CycloneDX SBOMs and
compatibility outcomes are retained privately under
`<external-root>/private/verification/python-image-remediation-20261121/final/`.
These local identities are not evidence of registry publication or attestation.

## nginx remediation

The earlier nginx scan found CVE-2026-86144 in libxml2 2.13.9-r2. Both nginx
Dockerfiles require at least 2.13.9-r3 and refresh signed Alpine packages through
[Alpine's officially listed HTTPS kernel.org mirror](https://mirrors.alpinelinux.org/).
The final web and edge images were rebuilt, smoke-tested and rescanned with zero
findings. Their application source and approved UI palette were not changed.

## Release enforcement and maintenance

The source gate runs the checksum-pinned Gitleaks CLI on the checkout and Git
history with redacted output. It needs no additional GitHub token or license.
Trivy blocks HIGH and CRITICAL vulnerabilities and infrastructure findings,
including unfixed findings. Release jobs rescan their built images before
publishing. CI uploads only selected verification reports from its runtime
directories. Private keys, owner credentials and raw runtime directories stay
outside the uploaded artifacts.

Images retain nonroot users, read-only deployment filesystems, dropped capabilities
and no privilege escalation. Python builds use checksum-pinned uv and locked
production dependencies. Build contexts allow only declared source/configuration
inputs. Release builds use `--pull --no-cache` to refresh package-update layers.
The pinned Python and SQLite package versions require explicit updates as vendor
releases change; a missing pinned package fails the build rather than falling back.

The release workflow checks each actual final Python artifact against disposable
TLS dependencies before scanning/publication. It retains sanitized compatibility
results and the complete vulnerability report. HIGH/CRITICAL findings, including
unfixed findings, still fail publication: `ignore-unfixed` remains false and there
is no blanket allowlist. Update pinned images/packages, rebuild, repeat artifact
checks and scan the exact new identities at release time. A passing local scan
does not authorize deployment or replace hosted release verification.

## Telemetry artifact remediation

The observability image lock contains five public digest-pinned runtime images.
Prometheus 3.16.0, Alertmanager 0.35.0 and Tempo 3.1.1 use public QuenchWorks
source-built images; their keyless signatures were checked against the
`quenchworks/images` GitHub workflow identity and GitHub OIDC issuer. Loki 3.7.10
and Collector 0.165.0 use upstream images. No registry login or paid account is
needed to pull these inputs.

Grafana 13.3.1 is built by `observability/grafana/Dockerfile`. It copies the pinned
publisher's patched server, web assets and exactly the three configured datasource
plugins onto the same supported Wolfi OS base as the applications. The source
vendor OS was rejected because Trivy has no advisory feed for it. The final
artifact has an actual Wolfi package inventory; copying a foreign package database
or changing the reported distro to make a scan pass is prohibited. Only the three
pinned rebuilt bundled plugins may load unsigned; arbitrary plugin downloads are
disabled. Grafana features used by OpsProof are verified by real datasource queries.

Complete scans require `--detection-priority comprehensive --list-all-pkgs` so
OS-owned Go binaries are included. The exact official scratch Collector contains
only its static binary, certificates and config; it has no OS package inventory.
All other runtimes require a supported OS feed and real package inventory.

Two raw HIGH findings in Grafana's bundled Tempo plugin arise from its Go
pseudo-version sorting below Tempo 2.x. Its embedded revision
`bcfe9f230c1de0f79cfd2110b38062e0f41c81e9` contains the upstream fixes for
CVE-2026-21728 and CVE-2026-28377. The gate rechecks each fix's ancestry and binds
OpenVEX `fixed` status to the exact artifact, source image, binary path, module,
version and vulnerability. A changed component, failed proof or new finding
receives no resolution. Raw reports, proof receipts and SBOMs are retained.
This is verified fixed source, not an exposure waiver or blanket ignore.

The final secured Grafana local image is
`sha256:433564068b98c82c05e6336512f0d22337c45de78568c7b0ba55ef04375901fe`.
All ten final application/telemetry artifacts passed the HIGH/CRITICAL policy;
the four application scans have zero findings at every severity. The telemetry
reports retain any lower-severity findings and the two source-proven fixed
mappings. Private current evidence is under
`<external-root>/private/verification/observability-20261121/`.

The existing owner-approved release now produces five artifacts, including
Grafana, with SBOMs and requested attestations. Cloud telemetry requires the
published Grafana digest from that exact-run manifest. Local source tags are
checked against the Docker context hash and actual image ID; they are not
presented as published registry digests. Publication and cloud acceptance remain
owner-run gates. The weekly observability workflow scans fresh advisory data;
Docker input updates remain part of the monthly dependency-review process.
