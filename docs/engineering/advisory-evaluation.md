# Advisory AI evaluation and release decision

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
