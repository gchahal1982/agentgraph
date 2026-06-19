"use client";

import { useState } from "react";
import { useAudit } from "@/lib/hooks";

export default function AuditPage() {
  const [runId, setRunId] = useState<string>("");
  const { data, isLoading } = useAudit(100, runId || undefined);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Audit log</h1>
      <input
        placeholder="filter by run id (optional)"
        value={runId}
        onChange={(e) => setRunId(e.target.value)}
        className="w-full bg-ag-bg border border-ag-border rounded p-2"
      />
      {isLoading && <p className="text-ag-muted">Loading…</p>}
      {data && (
        <table className="w-full text-left border border-ag-border rounded overflow-hidden text-xs">
          <thead className="bg-ag-panel text-ag-muted">
            <tr>
              <th className="p-2">ts</th>
              <th className="p-2">action</th>
              <th className="p-2">actor</th>
              <th className="p-2">run_id</th>
              <th className="p-2">payload</th>
            </tr>
          </thead>
          <tbody>
            {data.events.map((e) => (
              <tr key={e.id} className="border-t border-ag-border align-top">
                <td className="p-2 text-ag-muted whitespace-nowrap">
                  {new Date(e.ts * 1000).toLocaleTimeString()}
                </td>
                <td className="p-2 text-ag-accent">{e.action}</td>
                <td className="p-2">{e.actor}</td>
                <td className="p-2 text-zinc-400">{e.run_id.slice(0, 12)}…</td>
                <td className="p-2 text-zinc-300 max-w-md truncate">
                  {JSON.stringify(e.payload)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
