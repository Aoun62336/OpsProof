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

## Historical verification checkpoints

### Earlier runtime verification

The owner authorized additional API validation after the local fixes. Requests
were bounded, recorded before dispatch and stopped at the first failed gate.
No retries, tools, paid billing changes, cluster startup or cloud operations occurred.

| Configuration stage | Requests issued | Accepted and label-correct | Outcome |
|---|---:|---:|---|
| Corrected schema, low reasoning, 4,096-token ceiling | 3 | 2 | Third answer reached the token limit; stopped |
| Direct-answer mode, original decision prompt | 1 | 0 | Wrong empty-queue classification and duplicate evidence |
| Ordered rules and canonical evidence combinations | 9 | 8 | Unsupported-alert resume recommendation; stopped |
| Cause/action runtime policy check, direct-answer mode | 3 | 2 | Wrong cause rejected by the application policy check |
| Final ordered rules, low reasoning, 8,192-token ceiling | 10 | 10 | Independent narrow factual review passed |
| Complementary broad retest, same final source | 1 | 0 | Correct abstention, absent citation paths; stopped |

That earlier runtime request used temperature zero, low reasoning and an 8,192-token
ceiling. Ten runtime cases cover linked/unlinked worker holds, unpaused/unknown
holds, empty/missing queue, missing scrape, API/dependency unavailability and an
unsupported alert. All ten raw answers matched the frozen cause/action labels;
the application policy check accepted them. The reviewer identified no unsafe
recommendation or material unsupported claim in this final ten-case run.

The policy check rejects cause/action disagreements with fresh deterministic
evidence; it never rewrites a wrong answer into a passing one. Free-text grounding
and citation relevance still need factual review. Runtime evidence is constrained
to the 64 canonical subsets of six supported keys, enforcing unique references
without the provider's unsupported `uniqueItems` keyword. New evaluation epochs
bind approval to their exact canonical directory, inputs, source and prior receipts.

The final ten-case run reported 19,289 tokens (6,175 input and 13,114 completion).
The first five new stages together used26 requests and reported39,835 tokens.
The owner explicitly approved the complementary32-case batch, extending the
new-request ceiling to58. That batch stopped after one answer (2,923 tokens):
the unknown/abstained/none decision was correct, but two cited paths did not exist.
The500-character reason ended incompletely; finish_reason=stop and1,848 completion
tokens do not establish a max-token truncation. The reviewer identified no unsafe
action or definite invented measurement in that answer. Its raw label correctness
must not be reported as accepted output. Thirty-one cases were not issued.

All new stages together used27 requests and reported42,758 tokens (16,996 input,
25,762 completion). Earlier43 requests remain separate, for70 NVIDIA attempts
overall, with31 slots unused under the latest approved ceiling. No further calls
are scheduled or implied by those unused slots. Accounts/billing were not independently
audited; no paid service was enabled here.

This is development regression/application evidence after inspecting earlier
failures, not blind held-out performance or a production reliability guarantee.
The passing ten-case result does not replace the failed historical42-case runs.
At that checkpoint, full qualification was failed/incomplete; runtime enablement remained pending.
The next technical issue at that checkpoint was broad evidence-path selection and complete concise
explanations; this report does not claim those output defects are fixed. Exact private requests,
labels, source snapshots, receipts and independent reviews are retained under
`.runtime/verification/ai/`. No production image was rebuilt or deployed for these
changes; no Kubernetes or AWS infrastructure was started.

## Local integration corrections — 23 November 2026

The evaluator previously continued after mechanical or label failures even though
its acceptance gate required 100% success. It now stops at the first invalid
answer, contract mismatch or unsafe action, records the reason in the immutable
call receipt and run summary, and refuses restart. Runtime evaluation now uses
the same diagnosis parser as the application, including duplicate-reference
rejection. These were implementation defects; they must not be attributed to
the model or the owner's account configuration.

Schema translation now removes `uniqueItems` only as a schema keyword. It
preserves property/definition names and literal `const`, `enum`, `default` and
`examples` data. Expanding object alternatives rejects unsupported overlapping
constraints rather than silently replacing them. The property/literal defect is
reproduced locally; the frozen live schemas did not exercise those names, so it
does not explain their observed failures.

Fourteen new regressions failed against the prior source and passed after these
corrections. At that checkpoint, the offline suite passed 497 tests and 21 subtests, with
34 database integration tests skipped. No provider requests, image rebuilds,
cluster starts or cloud operations were performed for this correction. Historical
receipts and scores remain unchanged. This validates local safeguards, not live
model accuracy. AI remained disabled and live qualification was failed at that checkpoint.

### Original Groq/Gemini comparison

The owner authorized exactly 24 free-tier requests on 16 November 2026: twelve
cases each for Groq `openai/gpt-oss-120b` and Gemini `gemini-3.5-flash-lite`.
All 24 requests completed, with no retries, provider fallbacks or tools. The
owner confirmed paid billing disabled. Billing was not independently audited.
No further model requests are planned or authorized by this report.

## Decision

Neither provider meets the frozen qualification gate. Runtime AI stays disabled.
The existing deterministic evidence and human approval boundaries remain intact.
The broad reliability benchmark also does not qualify or enable the separate
narrow investigation adapter. The project can be prepared for deployment with
AI disabled; it must not advertise autonomous qualified AI diagnosis.

| Provider | Original regression, accepted correct | Held-out capacity, accepted correct | Mechanically accepted |
|---|---:|---:|---:|
| Groq | 3/8 | 3/4 | 8/12 |
| Gemini | 7/8 | 4/4 | 12/12 |

Acceptance includes valid schema, consistent abstention and resolvable citations.
All raw responses were basic-schema valid and specified `action: none`.
Groq had three citation-prefix failures and one `unknown`/non-abstention
inconsistency; those responses correctly failed closed. Its raw label agreement
must not be substituted for accepted output scores.

## Independent factual review

A separately approved read-only reviewer checked all answers, frozen sources,
labels, request/prompt/schema hashes and underlying held-out provenance. All
integrity checks passed. The reviewer received no keys and made no provider or
network calls. Mechanical path validation worked, but cannot validate arbitrary
reasoning in free text.

Three mechanically accepted answers made material unsupported inferences:

- Gemini's downstream answer claimed a measured threshold was met. The evidence
  supplied a timeout/trace and 400 ms timeout configuration, with no measured p95
  to establish the required >=0.5-second percentile.
- Both providers' faulty-release answers used the gateway-wide 28/86 error
  fraction as evidence of a candidate-only error threshold. The two populations
  are not interchangeable.

Capacity answers used message counts, waiting age in seconds and worker replicas
correctly. Neither provider confused pending/in-flight entries with undelivered
lag. Gemini handled the drained case consistently; Groq's inconsistent flag was
rejected. No unsafe operational instructions were found.

## Interpret the old labels carefully

The original eight cases remain unchanged regression evidence. Two historical
incident labels are in tension with the newly explicit quantitative contract:
the downstream record lacks measured p95, and the worker-failure record lacks a
container restart count and has zero undelivered messages. Pod replacement and a
second job attempt do not establish container restarts. Abstention can therefore
be defensible while disagreeing with these old incident labels. These scores do
not by themselves prove a model worsened or establish universal accuracy.

The four independently labelled held-out cases contain capacity observations
from three different trials, including correlated positive and drained KEDA
samples. They are retrospective and narrow. They support no prospective or
six-class generalization claim. Future AI enablement would require a separately
approved evaluation with labels and operational contracts aligned before calls;
no post-result relabelling, lower threshold or automatic provider change is used.

## Reproduction and retained evidence

Private frozen requests, labels, dispatch receipts, execution results and the
independent review are retained at `.runtime/verification/ai/comparison-v2/`.
The approved request SHA256 is
`9785377a20cc2dadec4d4527a319ee9688e4110e4abc413a1009d00c4888c983`.
The runner refuses to restart an already dispatched run and records unknown
interrupted outcomes before requests. Unit tests verify its 24-call ceiling,
HTTP failure stop behavior, approval/hash checks and interruption safeguards.
Provider keys and headers are absent from retained requests and review files.


## Next Gemini comparison: offline preparation, 22 November 2026

The owner approved local preparation and one independent read-only input
reviewer, not another round of model requests. The proposed candidates are
`gemini-3.8-flash` and `gemini-4-hydrogen`. The owner-supplied AI Studio dashboard
shows Free tier with 5 requests/minute, 250,000 input tokens/minute and
20 requests/day for each. These allocations do not prove successful access,
remaining quota or guaranteed capacity. Paid billing must remain disabled.

The preparation combines the unchanged eight original regression cases and four
previously reviewed capacity cases with 20 new synthetic contract checks. The
new checks have two positive examples for each of the five supported signatures
and ten abstention examples, covering wrong metric populations, missing measured
p95, Pod replacement versus container restarts, pending versus undelivered work,
short bursts, stale/future observations, collection errors and ambiguous signals.
The separate reviewer checked all 20 labels and all historical observations.
These are independently reviewed synthetic labels, not fresh real incident
holdouts; no new real-world or prospective accuracy claim is established.

Three historical incident labels differ from the current explicit evidence
contract: downstream latency lacks measured p95; worker failure lacks an explicit
container restart count and has no undelivered backlog; faulty release lacks a
candidate-only error fraction. The old labels and input bytes stay unchanged.
Private comparison labels record both historical identity and the separately
reviewed contract interpretation. Report these interpretations separately rather
than retrospectively replacing old benchmark scores.

`python -m scripts.reliability.prepare_gemini` freezes local request specifications,
private labels and a manifest under `.runtime/verification/ai/gemini-comparison/`.
`--check` revalidates byte hashes, code identity, model/input equivalence and typed
safety bounds. Historical provider source identity is checked using raw bytes or
explicitly recorded LF-normalized equivalence; the archived manifest and original
runner are never rewritten. The input-review receipt binds the reviewed fixture,
request and label hashes. API keys, headers and expected labels never enter the
model-visible facts.

The proposed total is 64 requests (32 per model), with 16 per model per quota day
over at least two daily quota windows. Requests would be serialized at least
30 seconds apart, with a 60-second timeout and 4,096 combined thinking/output
tokens at medium thinking level. There are no retries, fallbacks or tools. Other
project usage and shared quota pools must be checked before each daily batch;
quota or HTTP failure must stop that candidate rather than trigger a retry.

The preparer has no transport or execute branch and reads no credentials.
Offline response checks require explicit schema fields, consistent abstention,
exact resolvable citations, measured signature support, returned model identity
and token accounting. They cannot establish arbitrary free-text factual claims.
Actual provider compatibility, a reviewed bounded dispatch path, owner approval
of the frozen requests and independent factual output review remain outstanding.
Runtime AI stays disabled. This broad comparison also does not qualify the
separate narrow investigation adapter or waive independent real-incident gates.


## Gemini compatibility execution: 22 November 2026

The owner separately approved up to 64 free-tier requests, proof retention and
the same independent read-only safeguards/answer reviewer. Before dispatch,
555 Python/tooling tests and 21 subtests passed; 34 database integration tests
were skipped because no database or cluster was started. Lint, formatting,
frozen-input checks and the zero-call execution dry run passed. Independent
execution-safeguard review passed after correcting error-body retention and
adding journal-based missing-receipt detection and project-key fingerprinting.

Only the first two approved compatibility requests were attempted:

| Candidate | Recorded outcome | Answer / usage metadata |
|---|---|---|
| Gemini 3.8 Flash | ReadTimeout after the configured 60-second timeout; server outcome unknown | Not received |
| Gemini 4 Hydrogen | HTTP 503; no error body retained | Not received |

Both candidates stopped under the reviewed failure policy. There were no retries
or fallbacks; 62 frozen requests remain unissued. This is a provider/transport
failure, not a model diagnosis-quality failure. Accuracy is not evaluated.
Independent review verified request/specification hashes, reservations, dispatch
journal, 60.735-second start spacing and the stopped state. Factual output review
is NOT ASSESSABLE because no model answers exist. Token counters in the original
summary aggregate absent metadata; they must not be presented as measured zero
usage. The timed-out request may have been processed server-side.

Private proof is retained under `.runtime/verification/ai/gemini-comparison/`:
`owner-approval.json`, `execution-authorization.json`, independent review receipts,
`calls/001.json`, `calls/002.json`, `dispatch-journal.jsonl`, the completed console
log and test/check results. `compatibility-result.json` and `.html` explicitly
state unavailable usage and unevaluated accuracy. The checked `.png` is a local
report screenshot, not a provider-console screenshot. The final SHA256 index is
regenerated after console output and closeout artifacts finish, because the
in-process index preceded the final console-log bytes.

No new candidate is qualified or enabled. Paid billing was not activated; the
expected free-tier charge is $0 based on owner confirmation, not an independent
billing audit. No AWS resource was provisioned and no cluster was started.
The comparison remains incomplete. A separately approved recovery attempt would
need to preserve these failures and explicitly authorize any retry of a reserved
request; the runner never silently reissues an unknown outcome.


## Replacement-key recovery: 22 November 2026

The owner replaced GEMINI_API_KEY. A separately requested, authenticated model-list
GET returned HTTP 200 and listed both candidate model IDs. This establishes
metadata authentication, not successful generation or the cause of the earlier
failures. The key was neither displayed nor provided to the reviewer.

The owner explicitly approved two manual replacements, raising the cumulative
ceiling to 66 generation attempts and 17 per model per Pacific quota day. The
reviewed recovery epoch preserves the original finalized proof and source code,
uses one canonical sibling directory, binds the new approval/key/code identities,
and carries prior usage forward. Recovery-only dispatch remains capped at 16
per model per day. Full local checks passed: 571 tests, 21 subtests, lint and
formatting; 34 database integration tests were skipped without starting services.
Independent recovery-safeguard review passed before sending requests.

The two explicit replacement attempts again returned no diagnosis:

| Candidate | Replacement outcome | Answer / token metadata |
|---|---|---|
| Gemini 3.8 Flash | HTTP 503 | Not received |
| Gemini 4 Hydrogen | ReadTimeout after the configured 60-second timeout | Not received |

The recovery stopped both candidates without another retry or fallback. Across
the original and replacement epochs there are four generation attempts, zero
received answers and 62 approved generation requests still unissued. One separate
metadata authentication request is recorded independently. Token consumption is
unavailable, not measured zero. No inference-accuracy score can be established;
these outcomes do not prove either candidate makes incorrect diagnoses. Key
expiry has not been established as the cause of either epoch's failures.

Recovery proof is retained in the sibling directory
`.runtime/verification/ai/gemini-comparison-recovery/`, including owner approval,
preflight checks, independent reviews, hash-linked replacement receipts,
dispatch journal and a checked local report screenshot. Runtime AI remains
disabled and unqualified. Paid billing was not activated; expected free-tier
cost remains $0 based on owner confirmation, with no independent billing audit.
No AWS provisioning, cluster startup or provider-account purchase occurred.
The live comparison remains blocked by generation-service availability. The
remaining requests must not be automatically dispatched into the stopped epoch.


## Bounded generation diagnostics: 22 November 2026

The owner approved a small diagnostic batch within the existing 66-total and
17-per-model-per-Pacific-day ceilings. Eleven offline safeguard tests passed,
as did focused Ruff lint/format checks and independent read-only safeguards
review. No application runtime code or frozen benchmark requests were changed.

Only two new generations were sent: a one-word plain-text control to each model,
with low thinking, 1,024 maximum output tokens, candidateCount=1 and a 120-second
read timeout. Neither control included OpsProof evidence, a system instruction
or a JSON output schema. Gemini 3.8 Flash returned ReadTimeout after 120.682
seconds; Gemini 4 Hydrogen returned ReadTimeout after 120.363 seconds. No HTTP
status, provider error message, final answer or usage metadata was received.
Both candidates stopped. The full frozen body was NOT tested at 120 seconds;
the schema and thinking isolation stages were NOT reached.

The failure therefore also occurs without OpsProof incident facts or a response
schema. Its exact cause remains unresolved: these observations do not isolate
the provider backend, network path or remaining request parameters. In
particular, Google's troubleshooting guide says candidate-count control is
unsupported on Gemini 3/4, while the generic GenerateContent reference defines
candidateCount with default 1. Both original and diagnostic requests retained
candidateCount=1; its acceptance is not established by a timeout. No expired key,
configuration mistake, global outage or model reasoning failure is proven.

Across these three epochs there are six generation attempts and 60 unused from
the approved ceiling of 66; each model has three recorded attempts on this
Pacific quota day. Accuracy remains unevaluated and token consumption remains
unavailable, not measured zero. The two stopped benchmark epochs must not be
automatically resumed, and any future approved execution must count diagnostics.

Private proof is under `.runtime/verification/ai/gemini-diagnostics/`, including
reviewed code/tests, approval, two receipts, console/test logs, diagnosis JSON,
independent review and a visually checked local report screenshot. All 31
original and 19 recovery indexed proof files were verified unchanged. Runtime
AI remains disabled; no paid billing, cluster startup or AWS provisioning occurred.

The next useful check is a bare prompt in Google AI Studio with the same
project/model. A successful browser result would justify a separately authorized
API-versus-browser control without optional generation parameters; another
failure would provide provider-console evidence. Neither result alone qualifies
the model or completes the frozen incident comparison.

Primary references: [Google troubleshooting](https://aistudio.google.com/docs/troubleshooting)
and [GenerateContent reference](https://aistudio.google.com/api-reference/generate-content).


## Native-client controls and owner playground evidence: 22 November 2026

Following the owner's further root-cause request, two additional explicit controls
used Windows native curl with certificate verification enabled, no proxy,
redirects or retries, and stdin-only credentials. The request contained the short
prompt and a 1,024-token output ceiling; thinking, candidateCount, schema and
system settings were omitted. Seven offline safeguard tests and independent
read-only safeguards review passed before execution. These controls changed both
client/TLS implementation and optional parameters, so neither individual causal
effect is isolated by a changed result.

Gemini 3.8 Flash returned HTTP 503, code 503, status UNAVAILABLE, in 2.333 seconds.
Google's sanitized message explicitly reported that the model was experiencing
high demand and advised trying later. Provider-reported demand is therefore
confirmed for this request. It does not prove the cause of every earlier timeout,
an account-wide outage or a full frozen-request compatibility result.

Gemini 4 Hydrogen completed DNS/TCP/TLS setup in approximately 8/45/97 ms, but
curl received zero response bytes before its 120-second limit (exit 28, HTTP 000).
The observed failure is a response wait after TLS setup; the underlying backend
or return-path cause remains unresolved. The owner's screenshot shows Hydrogen
answering three short playground messages with Low thinking. This establishes
playground availability in that session, not equivalence of project, API-key
access, request body or quota pool with the API tests.

There are eight agent-controlled generation attempts, four of them diagnostic,
and 58 unused from the 66-agent-attempt ceiling. Three visible owner playground
requests are recorded separately; conservatively adding them to the same
Hydrogen quota pool yields seven observed requests, below the daily ceiling of
17. Other project usage is not independently verified. No API diagnosis or usage
metadata was received, so inference accuracy is still not evaluated. Runtime AI
remains disabled; no paid billing activation, AWS provisioning or cluster startup
occurred. Neither stopped benchmark epoch was resumed.

Private receipts, redacted provider errors, client timings, tests, reviews and
the owner-provided screenshot are retained under
`.runtime/verification/ai/gemini-native-controls/`. All 64 previously indexed proof
entries were verified unchanged. The working implementation was not rewritten
in response to provider high demand, and no model was qualified by greetings.


## NVIDIA connectivity: 22 November 2026

After the owner supplied the NVIDIA key, one separately authorized request to
`nvidia/nemotron-3.5-super-vl-120b-a12b` returned HTTP 200 in 0.926 seconds and
`{"status": "OK"}` under a tiny strict JSON schema. The request used reasoning
effort none and a 256-token output ceiling, with no tools, retries or fallbacks.
Received usage was 30 prompt tokens and 7 completion tokens, 37 total.

The provider's response model field was
`private/nvidia/nemotron-3.5-super-120b-a12b`. This alias is preserved; it is not
presented as an exact model-ID match. Identity reconciliation, the full runtime
diagnosis schema and bounded incident-quality evaluation remain pending. A
successful connectivity response does not qualify runtime AI.

Private proof is `.runtime/verification/ai/nvidia-connectivity/`: the reviewed
operator check, one durable reservation/result, console log, verification receipt
and SHA256 index. The active key is absent from these files. Runtime AI remains
disabled; no billing settings were changed, no cluster was started and no AWS
resources were provisioned. The official catalog marks this endpoint free;
account billing has not been independently audited.


## NVIDIA bounded evaluation and corrections: 23 November 2026

The frozen protocol covered ten authored runtime cases plus eight historical
regression, four retrospective capacity and twenty synthetic contract cases.
Independent input/safeguard review preceded dispatch. The run stopped after
37 attempts when request 037 timed out after approximately 121 seconds. There were
36 received answers, 16 mechanically accepted and 10 accepted/correct. Runtime
cause/action agreement was 4/10, while all ten action recommendations matched
the supplied permission boundary. Three independent factual failures were
identified: a false claim that other resume prerequisites passed, invented
consumer unavailability from job counts, and substitution of gateway-wide errors
for a missing candidate-only error fraction. No unsafe action recommendation
was recorded. This is a failed, incomplete qualification; five original cases
remain unissued. Labels and failed responses were not modified.

The implementation now explains cause labels independently of stricter action
eligibility, clarifies metric units and missing-versus-zero values, transmits
job-link uniqueness without identifiers, and rejects duplicate citations locally.
Broad explanation length and abstention relationships are declared in the schema
and checked locally. Endpoint/requested-model/registered-serving identity is
pinned. Exact checkpoint, weights, precision and vision remain unverified.

One subsequent control returned HTTP 400 with NVIDIA's exact grammar error:
`Unimplemented keys: ["uniqueItems"]`. Its receipt remains preserved. NVIDIA's
wire adapter omits that keyword while local validators retain duplicate rejection.
Four further diagnostic controls returned HTTP 200; only one passed all local
checks. One omitted three required fields, one had no retained assessable answer
with completion usage 4096, and one was rejected for a duplicate citation. The
missing finish reason prevents asserting truncation for that no-answer case.
These are diagnostic controls designed after observed failures, not blind holdouts.

The final offline normalization spells out complete object alternatives rather
than relying on inherited parent properties in oneOf. This preserves all examined
application constraints except intentionally wire-omitted uniqueness; independent
structural checking found zero acceptance mismatches across 2,592 samples. That
small checker is not a full JSON Schema validator or provider grammar execution.
Future diagnostics retain bounded, scrubbed finish and parse metadata. These
last source changes have NOT been validated by another live model request.

NVIDIA accounting is 1 connectivity + 37 initial + 1 grammar-rejected + 4 compatibility =
43 attempts; the ceiling is exhausted. Received usage totals 26,927 input and 71,135
completion tokens, 98,062 total. Timeout and HTTP 400 usage are unavailable, not
measured zero. The selected catalog endpoint is free for development/evaluation;
no billing change was made and account billing was not independently audited.

Final source checks passed 483 tests and 21 subtests, with 34 database integration
tests skipped. Lint, formatting and git diff checks passed. No cluster was
started, no AWS resource provisioned, and no production image rebuilt/deployed.
A newly frozen, owner-authorized full evaluation and independent factual review
are required before runtime AI can be enabled. No test threshold was lowered.

Private proof: `.runtime/verification/ai/nvidia-evaluation/`,
`.runtime/verification/ai/nvidia-contract-controls/`, and
`.runtime/verification/ai/nvidia-schema-compatibility/`. Each phase preserves the
source actually evaluated; it differs from later corrected source. Historical
scores must not be assigned to the newer code or merged with diagnostic controls.
