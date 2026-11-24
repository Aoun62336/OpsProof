# Reliability verification

Bounded trials, independent evidence, load/capacity analysis and source/image checks.

Run from the repository root using the locked control-plane tooling environment:

```sh
uv run --project apps/control-plane --locked python -m scripts.reliability.MODULE
```

Tests live in `tests/`. See [repository structure](../../docs/engineering/repository-structure.md) and the [operations guides](../../README.md#local-operation). Use an explicit local/cloud context; never infer cloud authorization from a passing source test.

`validate_python_image --component demo|control --image LOCAL_REFERENCE` exercises
the installed artifact against disposable, network-isolated PostgreSQL and Redis
with TLS. It requires Docker, the pinned fixture images and 2 GiB free host RAM;
it never starts Kubernetes or uses provider keys. Results include runtime library
versions, positive/negative connection checks, actual API/worker behavior and
SIGTERM exit status. Owned containers and generated private keys are removed.
The release workflow runs this check for both Python artifacts before publication.

`qualify` runs the frozen deterministic reliability checks without credentials or
external calls. The Gemini/Groq execution and recovery commands are retired.
Their source checkpoint and immutable historical receipts remain private under
`.runtime/verification/ai/`. Historical comparisons do not qualify another model.

The optional runtime adapter supports NVIDIA's hosted Nemotron chat-completions
endpoint with schema validation, no tools and no automatic retries. Configure
`OPSPROOF_CONTROL_AI_PROVIDER=nvidia`, the exact NVIDIA catalog model identifier,
and `OPSPROOF_CONTROL_AI_API_KEY` in the private environment. AI remains disabled
until a separately bounded live evaluation is approved and passes. No NVIDIA
request was sent during provider retirement. `evaluate_advisory` provides the frozen, single-epoch NVIDIA evaluation path;
preparation/checking is offline and execution requires an exact independent
review. It uses immutable inputs, source pins, pre-send reservations and a fixed
request ceiling. The recorded run is stopped and failed qualification. Later
source corrections intentionally differ from its evaluated-source snapshot:
`--check` refuses such drift, and the old run must never be resumed or silently
reissued. Its historical inputs require the explicitly hash-bound private evidence
bundle from the earlier comparison; they are not application runtime dependencies.
Fresh qualification requires a separately approved protocol/freeze. The offline
`qualify` command never calls a provider.

The evaluator stops on the first mechanical failure, contract mismatch or unsafe
action because any such failure makes its 100% acceptance gate unattainable.
The failed call receipt and summary retain a stop reason; restart stays prohibited.
Runtime answers use the application's diagnosis parser, including evidence-reference
uniqueness checks. Offline safeguard tests do not qualify live model accuracy.

Each new epoch uses an explicit `--run-name`; its independent review binds the
exact manifest and canonical evidence directory, preventing copied approvals
from creating a fresh allowance. `--prior-attempts` records actual earlier calls,
and `--empty-queue-first` puts that regression first without changing labels.
Prior failed directories and source snapshots must remain intact.

An earlier runtime configuration used low reasoning, temperature zero and an
8,192-token ceiling. Its ten authored runtime cases passed live and independent
factual review. The application separately rejects cause/action disagreements
with deterministic policy; this does not validate arbitrary prose. Full model
qualification remains incomplete: the separately approved broad batch stopped at
its first answer because cited paths were absent;31 requests were not issued.
The correct raw abstention does not count as accepted output. Its explanation
also ended incompletely at500characters; this was not max-token truncation.
The owner approved32 requests, extending the new ceiling to58, but only27 new
requests were used across all stages. Unused slots imply no scheduled calls. Runtime AI
remains disabled; no production image rebuild or deployment is claimed.

The final sparse-citation source passed the frozen 42-case NVIDIA development
qualification on 24 November 2026, with independent factual review. Broad wire
citations select 1–6 existing true-only keys for positive findings, or 0–6 when
abstaining; decoding preserves the public list. Both profiles request low reasoning:
8,192 runtime / 16,384 broader tokens, with temperature 1.0/top_p 0.95 and
best-effort seed 42. Strict local validation remains independent of provider grammar.
The later pre-cloud closeout passed 550 tests and 21 subtests; all 36 SQL-only
cases passed separately. Updated local artifacts were built and tested. Runtime
AI stays disabled, and no registry publication or deployment is claimed. This is regression evidence,
not unseen-incident accuracy. See the [current decision](../../docs/engineering/advisory-evaluation.md).
Historical stopped epochs and source snapshots remain intact and cannot be
resumed or silently rescored under the passing source. The final 42 raw answers,
source/input hashes, independent reviews and exclusive offline closeout receipt
are retained in the private runtime evidence bundle.
