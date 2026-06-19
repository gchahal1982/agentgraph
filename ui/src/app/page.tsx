export default function Home() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-bold">AgentGraph</h1>
        <p className="text-ag-muted mt-2">
          Agent runtime for business outcomes. Packaged verticals for sales
          ops, support ops, compliance, recruiting, insurance, construction,
          and healthcare.
        </p>
      </section>

      <section className="grid grid-cols-3 gap-4">
        <a href="/agents" className="block p-4 bg-ag-panel border border-ag-border rounded hover:border-ag-accent">
          <h2 className="text-ag-accent font-bold">Agents</h2>
          <p className="text-ag-muted mt-1">Browse the registered agent registry.</p>
        </a>
        <a href="/threads" className="block p-4 bg-ag-panel border border-ag-border rounded hover:border-ag-accent">
          <h2 className="text-ag-accent font-bold">Threads</h2>
          <p className="text-ag-muted mt-1">View runs by thread id; resume paused handoffs.</p>
        </a>
        <a href="/audit" className="block p-4 bg-ag-panel border border-ag-border rounded hover:border-ag-accent">
          <h2 className="text-ag-accent font-bold">Audit</h2>
          <p className="text-ag-muted mt-1">Inspect every model, tool, and policy event.</p>
        </a>
      </section>

      <section className="bg-ag-panel border border-ag-border rounded p-4">
        <h2 className="font-bold mb-2">Quick start</h2>
        <pre className="text-xs whitespace-pre-wrap text-zinc-300">{`# Start a vertical service
uv run ag-sales-ops --port 8081 &

# Or run the canonical server (agents registered at startup)
uv run agentgraph-server

# Then call it from anywhere
curl -X POST http://localhost:8080/threads/abc/run \\
  -d '{"agent": "qualify_lead", "input": {"contact_email": "ada@analytix.com"}}' \\
  -H 'content-type: application/json'`}</pre>
      </section>
    </div>
  );
}
