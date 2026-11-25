# OpsProof operator console

The React/TypeScript console uses authenticated same-origin control API requests.
It presents workload, deployment, capacity and runbook cards, incidents,
investigations, experiments and independently recorded trial evidence.

Use Node.js 24 and the committed npm lockfile from this directory:

```sh
npm ci
npm run dev
npm run lint
npm run test
npm run build
```

Vite binds to loopback port 5173 and proxies `/api` to the existing control API at
`127.0.0.1:8090`. Production Nginx serves built assets and proxies to the private
control Service. Login uses an HttpOnly session; mutations include CSRF. Never
embed provider keys, database credentials or operator secrets in the build.

Original forest/porcelain tokens and local font packages define the palette.
Backend capabilities supply environment labels and disabled controls. Cloud
observation does not enable recovery or AI.

Vitest covers units; the owned API/database fixture runs Playwright and axe at
five widths. See [verification](../../docs/operations/reliability-verification.md).
Browser screenshots are local test evidence, not AWS deployment proof.
