# Advisory AI evaluation and release decision

## Current qualification: 24 November 2026

The exact frozen NVIDIA source passed all 42 development regression cases:

| Scope | Issued | Mechanically accepted and label-correct | Independent factual review |
|---|---:|---:|---|
| Narrow runtime cause/action | 10 | 10 | Passed |
| Historical regression | 8 | 8 | Passed |
| Retrospective capacity | 4 | 4 | Passed |
| Synthetic evidence contract | 20 | 20 | Passed |

The reviewer checked raw answers against frozen observations and labels: zero
material unsupported claims and zero unsafe recommendations. This is 100% of
the agreed suite, not a guarantee on future incidents. Previously inspected
cases are development regression evidence; the four historical holdouts are
not fresh blind holdouts now. Exact hosted checkpoint, weights, precision and
vision capabilities were not verified.

Runtime AI remains disabled. Model output cannot authorize operations. Enabling
the optional runtime adapter and validating a rebuilt deployment are separate
operational decisions. This qualification did not deploy an image. The subsequent
pre-cloud closeout built and tested local artifacts containing the qualified
source; see [the release closeout](verification.md). Nothing was published or
deployed to Kubernetes or AWS.

## Contract and implementation

The adapter uses NVIDIA's pinned hosted endpoint, requested catalog model
`nvidia/nemotron-3.5-super-vl-120b-a12b`, and registered serving identifier
`private/nvidia/nemotron-3.5-super-120b-a12b`. Both profiles request low reasoning,
temperature 1.0, top_p 0.95 and best-effort seed 42. Runtime output is bounded at
8,192 tokens; the broader read-only classifier uses the documented 16,384-token
default. Read-inactivity limits are 120/240 seconds respectively, not hard total
wall-clock deadlines. There are no retries, provider fallbacks or tools.

Metric units, reference-clock freshness, service thresholds, missing/null values
and the public exactly-one-signature rule are explicit. Deterministic policy
rejects runtime cause/action disagreement without rewriting the model answer.

NVIDIA rejected array uniqueItems in an earlier grammar control. Runtime evidence
therefore uses canonical unique subsets of six permitted keys. Broad wire
citations now use a sparse object of actual evidence paths with true-only values,
maxProperties 6, and minProperties 1 for positive findings. The current live run
accepted these keywords. Strict parsing rejects duplicate keys, invented paths,
false/non-Boolean values, too many citations and empty positive selections.
Decoding only projects keys to the unchanged public list; it never repairs a
failed answer. Existing parent objects can support absence claims. Context and
contract metadata are excluded from observation citations. Free prose grounding
requires independent review beyond schema/path validation.

The reviewer identified a remaining precision limitation: some selected paths
were nondecisive or omitted a numeric field discussed in otherwise supported
prose. Path existence is not complete claim-to-citation coverage. One answer
called stream messages waiting jobs; this must not be read as a count of distinct
durable jobs because multiple stream entries can refer to the same job ID. These are retained review
observations, not a claim of perfect prose or proven causal diagnosis.
One future-dated observation correctly caused abstention, but its explanation
called the freshness problem stale or missing instead of future-dated. The
decision was correct; that freshness subreason was imprecise.

## Verification and retained failures

550 Python/script tests and 21 subtests passed; 34 disposable-database tests were
skipped. Application/script lint, format and git diff whitespace checks passed.
The first closeout format check found one mixed line ending in qualify.py. It
was normalized after the live run, preserving the evaluated snapshot. The failed
format logs remain in `.runtime/verification/ai/ai-qualification-final/`. Independent
review and offline replay establish identical normalized source/AST and all 42
exact API bodies. The closeout records both source hashes; the maintained runner
still rejects byte-level drift and cannot resume that completed run.
No Kubernetes cluster was started, AWS resource provisioned, paid service enabled
or provider key exposed. Billing was not independently audited.

| Earlier separate epoch | Attempts | Accepted and correct | Reason stopped |
|---|---:|---:|---|
| Interrupted full run | 5 | 4 received | One reserved outcome unknown |
| Clarified array citations | 17 | 16 | Duplicate citation |
| Fixed Boolean map | 15 | 14 | Generation limit at 8,192 |
| Vendor sampling with fixed map | 24 | 23 | Generation limit at 8,192 |
| Rejected direct broad profile | 4 | 3 | Missed database signature and unsupported zero count |
| Low reasoning, 16K, fixed map | 3 | 2 | Positive finding selected no citations |
| Final sparse citations | 42 | 42 | Completed and independently reviewed |

Earlier 70 NVIDIA attempts remain accounted separately, for 180 overall and
110 in this finalization task. One interrupted outcome has unknown usage; other
historical missing usage remains unknown. Earlier results were not overwritten,
rescored or merged into the final 42-case score. Sampling alone did not resolve
truncation; no stronger causal claim is established by these observations.

Private proof is under `.runtime/verification/ai/nvidia-sparse-verification/`:
hash-bound requests, labels, evaluated source, independent preflight, owner scope,
pre-send reservations, raw answers and final factual review. The exclusive
`.runtime/verification/ai/ai-qualification-verified/` closeout records offline replay,
commands, hashes and preservation checks without rewriting historical indexes.

## Worker ownership and activation boundary

The evidence process serializes runtime provider dispatch using a PostgreSQL
session advisory lock, retained across the committed running claim and response.
Only the owner may reconcile abandoned running work. Without a live owner, work
older than 180 seconds is marked failed with an unknown outcome; it is never
automatically queued again. The grace is above the runtime HTTP timeouts, not a
claim of a hard wall-clock request deadline. Connections release ownership before
returning to the pool, or are discarded if cleanup fails.

The repository finalization changes collection and worker ownership, not the
qualified model request, decoder or deterministic decision contract. Offline
regression and real SQL concurrency checks cover those changes. No new provider
evaluation is implied or authorized. Runtime AI remains disabled.

Earlier checkpoint narratives, failed answers, unknown requests and frozen
evaluation inputs are retained in private evidence. See the
[retention guide](repository-structure.md#generated-files-and-retention) for
archive locations. Use this decision and the current tooling for activation or
future qualification.
