# Container security and release gate

Reviewed 21 November 2026. Runtime images use pinned base digests, nonroot users,
read-only filesystems, dropped capabilities and no privilege escalation. Python
builds use a checksum-pinned uv image and locked production dependencies. Build
contexts allow only declared source/configuration inputs. Release builds use
`--pull --no-cache` so package-update layers are refreshed for the release.

The complete scan includes unfixed findings. The release policy rejects every
HIGH/CRITICAL finding; `ignore-unfixed` is false and no blanket allowlist was added.
A complete JSON report is retained before the publication gate. Local successful
builds/tests do not override that security gate.

## Available fix

The fresh nginx scans detected CVE-2026-86144 in libxml2 2.13.9-r2. Both nginx
Dockerfiles now require at least 2.13.9-r3 and refresh Alpine packages. Exact
rebuilt image IDs and rescan outcomes are retained in the current private
verification reports; an earlier scan is not evidence for a changed image.

## Residual Python-base findings

The initial fresh scan found 47 HIGH package/advisory occurrences in each Python
image, representing eleven distinct CVEs. No CRITICAL finding or available
HIGH/CRITICAL package fix was reported for these Debian trixie images. This is
not a claim that the packages are safe or that no exploit exists. Review again
at release time and whenever the base, deployment permissions or inputs change.

| Advisory | Trigger/exposure review | Disposition |
|---|---|---|
| CVE-2026-76642 | Privileged mount helper/post-hook operation | Unfixed; release blocked |
| CVE-2026-78408 | Privileged nsenter/cgroup descriptor inheritance | Unfixed; release blocked |
| CVE-2026-78409 | fstab-authorized mount/subdirectory traversal | Unfixed; release blocked |
| CVE-2026-78410 | Privileged bind-mount/source-path replacement | Unfixed; release blocked |
| CVE-2026-54369 | Privileged pathname-based ACL operation | Unfixed; release blocked |
| CVE-2025-69720 | Crafted input to the ncurses infocmp tool | Unfixed; release blocked |
| CVE-2026-119373 | SQLite FTS5 prefix queries/negative row IDs | Unfixed; release blocked |
| CVE-2026-119374 | Corrupted SQLite FTS5 index with secure delete | Unfixed; release blocked |
| CVE-2026-119379 | Crafted SQLite session changesets | Unfixed; release blocked |
| CVE-2026-16742 | systemd-homed-managed local user/group handling | Unfixed; release blocked |
| CVE-2026-9538 | Perl Archive::Tar reading a crafted large tar entry | Fix deferred by distribution; release blocked |

The application uses PostgreSQL, not SQLite for persistence. Source inspection
found no application invocation of mount/nsenter, systemd-homed, infocmp or Perl
tar processing. Nonroot/no-new-privileges/capability restrictions reduce the
privileged-operation exposure. These are bounded exposure observations, not
formal proof of non-exploitability, and do not justify silently deleting package
metadata, using forced package removal, switching distributions or waiving CVEs.

The Debian tracker confirms that the current trixie package remains vulnerable
for the [mount advisory](https://security-tracker.debian.org/tracker/CVE-2026-76642)
and [SQLite advisory](https://security-tracker.debian.org/tracker/CVE-2026-119373),
and records [Perl fix deferral](https://security-tracker.debian.org/tracker/CVE-2026-9538).
Scanner severity and a distribution's urgency classification are different facts.

## Conditions for release

Prefer supported vendor fixes, rebuild all affected images and rescan the exact
new identities. If no supported fix exists, any alternative base/package change
needs compatibility validation; any narrowly scoped exception needs a separate
owner decision with exact CVE/package/image digest, supported exposure evidence,
controls, review expiry and revocation conditions. No exception is approved by
this document. The present HIGH findings keep image publication/cloud deployment
blocked until that work or decision is completed. Do not force-remove essential
base packages or install packages from Debian unstable to make a scanner green.
