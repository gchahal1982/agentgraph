# AgentGraph UI

Next.js dashboard for AgentGraph.

- **/**            Home, quick start
- **/agents**      Browse registered agents
- **/threads**     Run an agent in a thread
- **/audit**       Inspect the audit log

The UI proxies `/api/*` to the Python server (default
`http://localhost:8080`). Configure with `AGENTGRAPH_SERVER`.

## Develop

```bash
cd ui
pnpm install
pnpm dev
# open http://localhost:3000
```

## Build

```bash
pnpm build
pnpm start
```
