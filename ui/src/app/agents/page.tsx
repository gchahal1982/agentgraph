"use client";

import { useAgents } from "@/lib/hooks";

export default function AgentsPage() {
  const { data, error, isLoading } = useAgents();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Registered agents</h1>
      {isLoading && <p className="text-ag-muted">Loading…</p>}
      {error && <p className="text-red-400">Failed to load agents.</p>}
      {data && data.agents.length === 0 && (
        <p className="text-ag-muted">
          No agents registered. Start a vertical service to register one, e.g.{" "}
          <code className="text-ag-accent">uv run ag-sales-ops</code>.
        </p>
      )}
      {data && data.agents.length > 0 && (
        <table className="w-full text-left border border-ag-border rounded overflow-hidden">
          <thead className="bg-ag-panel text-ag-muted">
            <tr>
              <th className="p-2">Name</th>
              <th className="p-2">Vertical</th>
              <th className="p-2">Description</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((a) => (
              <tr key={a.name} className="border-t border-ag-border">
                <td className="p-2 text-ag-accent">{a.name}</td>
                <td className="p-2">{a.vertical}</td>
                <td className="p-2 text-zinc-300">{a.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
