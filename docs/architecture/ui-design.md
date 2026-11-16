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

## Temporary Brand Mark

The OP monogram is temporary and will be replaced
with the final supplied brand logo.

## Current Data Scope

The current UI displays control-plane experiment
records, execution states, event histories and reports.

Kubernetes telemetry, incident correlation,
AI diagnosis and cloud cost information are not yet
integrated into the dashboard.

## Verification

Source implementation prepared.

Runtime, visual, responsive, accessibility and CI
verification must be recorded after execution.

## Local results ? 2026-11-05

Backend lint and 17 tests passed; frontend lint, 3 unit tests and production build passed. Browser branding, accessibility, real navigation, mobile Escape/focus and desktop controls passed. Four required viewport sizes were checked for overflow on login, Overview, Experiments and Evidence. Screenshots and real exported evidence are under ignored `.runtime/redesign/`. A real experiment was created through the UI and independently verified. Missing/invalid CSRF returned 403; successful logout returned the login screen and revoked the session.

Corrections found during execution: use the existing darker ink token for the login hint; match the navigation label exactly in Playwright; preserve the active auth query when removing private cached records on logout.
