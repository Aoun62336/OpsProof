# Public evidence

The [verification guide](../engineering/verification.md#local-results-and-screenshots) links the original
local UI screenshots and the benchmark calculations.

`cases.json` contains one sanitized historical local trial for each of the six
scenario classes. It is prepared for review, not approved for public release.
It records actual independent receipt digests, tested source-tree hashes and
uncommitted-source status. It makes no current-cloud or AI qualification claim.
Private source bindings remain in ignored runtime storage; raw trial artifacts,
keys, account information and live operator URLs are excluded.

Before publication, rerun `scripts.cloud.verify_curated_evidence` with the
private bindings, render the site, run `verify_public_replay`, inspect it visually
and have the owner review privacy and claims. The Pages workflow requires the
exact reviewed JSON hash at the approved main commit and a protected deployment.
Automated lineage and sanitizer checks do not replace that review.
