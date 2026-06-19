import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentGraph",
  description: "Agent runtime for business outcomes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-ag-bg text-zinc-100 font-mono text-sm antialiased">
        <header className="border-b border-ag-border bg-ag-panel">
          <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-6">
            <a href="/" className="text-ag-accent font-bold">agentgraph</a>
            <nav className="flex gap-4 text-ag-muted">
              <a href="/agents" className="hover:text-zinc-100">Agents</a>
              <a href="/threads" className="hover:text-zinc-100">Threads</a>
              <a href="/audit" className="hover:text-zinc-100">Audit</a>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
