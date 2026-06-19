"use client";

import { useState } from "react";
import { useThreads } from "@/lib/hooks";

export default function ThreadsPage() {
  const { data } = useThreads();
  const [threadId, setThreadId] = useState<string | null>(null);
  const [agent, setAgent] = useState("qualify_lead");
  const [input, setInput] = useState('{"contact_email": "ada@analytix.com"}');

  async function runAgent() {
    if (!threadId) {
      const r = await fetch("/api/threads", { method: "POST" });
      const j = await r.json();
      setThreadId(j.thread_id);
    }
    const tid = threadId ?? (await (await fetch("/api/threads", { method: "POST" })).json()).thread_id;
    const r = await fetch(`/api/threads/${tid}/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent, input: JSON.parse(input) }),
    });
    const j = await r.json();
    alert(JSON.stringify(j, null, 2));
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Threads</h1>

      <section className="bg-ag-panel border border-ag-border rounded p-4 space-y-2">
        <h2 className="font-bold">Run an agent</h2>
        <label className="block">
          <span className="text-ag-muted text-xs">Agent</span>
          <input
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            className="block w-full bg-ag-bg border border-ag-border rounded p-2 mt-1"
          />
        </label>
        <label className="block">
          <span className="text-ag-muted text-xs">Input (JSON)</span>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="block w-full bg-ag-bg border border-ag-border rounded p-2 mt-1 h-24"
          />
        </label>
        <button
          onClick={runAgent}
          className="bg-ag-accent text-ag-bg font-bold px-4 py-2 rounded"
        >
          Run
        </button>
      </section>

      <section>
        <h2 className="font-bold mb-2">Existing threads</h2>
        <p className="text-ag-muted text-xs">
          {data?.threads?.length ?? 0} thread(s) tracked on this server.
        </p>
      </section>
    </div>
  );
}
