# OpsProof UI Design System

## Identity

Name: OpsProof

Descriptor: Cloud Reliability & Safe Operations

Tagline: Every recovery deserves proof.

Design system: Forest & Porcelain

## Typography

- Instrument Sans: interface text, navigation and data
- Newsreader: editorial branding and selected headings
- IBM Plex Mono: technical identifiers and evidence

## Brand Colors

- Forest: #121D19
- Moss: #30453A
- Porcelain: #F2F0E9
- Ivory: #FCFAF6
- Bronze: #B18F75

## Operational States

- Queued: #525862
- Running: #245BDB
- Verifying: #7137B8
- Succeeded: #0F7B46
- Failed: #BE263A
- Warning: #A75A00

Operational colors must communicate meaning independently
from brand colors. Every state also requires readable text.

## Design Principles

1. Evidence before visual decoration.
2. Real operational state only.
3. Compact, readable information hierarchy.
4. Distinct desktop and mobile presentations.
5. Shared components and centralized design tokens.
6. Accessible focus and keyboard interactions.
7. No fabricated metrics or healthy-state assumptions.
8. Restrained motion and reduced-motion support.

## Brand mark and current data scope

The OP monogram is the current implemented mark. No replacement asset is required.
The operator workspace includes experiments, incidents, investigations, approvals,
evidence and a read-only trial ledger. Workloads, Deployments, Capacity and Runbooks
use operational cards with explicit observation state and backend capabilities.
The environment label comes from the authenticated API, not a fixed local label.

Capacity reservations are configuration, not measured utilization or cloud billing.
Unavailable integrations and stale/missing observations remain explicit. Cloud
runbooks are read-only; AI and recovery defaults remain disabled. The trial page
explains when its ledger is disabled. No synthetic healthy state is displayed.

## Verification

Current tests and dated production-build/browser results are recorded in
[engineering verification](../engineering/verification.md). A source/build check
does not establish live Kubernetes or cloud behavior. Historical UI outcomes and
original image/source identities remain in
[the UI acceptance record](../history/workspace-ui-and-offline-evidence.md).
The Forest & Porcelain tokens in `apps/web/src/styles/tokens.css` remain authoritative.
