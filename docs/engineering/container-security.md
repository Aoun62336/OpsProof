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

Application source, Python lockfiles and migrations are unchanged. The glibc
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
demo     sha256:adc4857095bf8b1f72fccdf417b6c24b66cc74dcca550cc1724e510d5a8a621b
control  sha256:b10af69b63b7547869404e83fab9ced750e4ea447c8af3f1c4538e66ca9dbcce
web      sha256:66834b10906ad2c2d594c615ae78eebb8a9b59ee2c7f1512ae573a64904ddda7
edge     sha256:e2d324b978364760737a19a94d2c8ef930c6ac95bbe4b5e5dbf0bf2f572d6e9d
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
