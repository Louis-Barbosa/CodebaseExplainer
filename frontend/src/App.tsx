import { useEffect, useRef, useState } from "react";
import type React from "react";
import { explain, followup, getBackends } from "./api";
import type { Backends, ChatTurn, Overview } from "./types";
import { Mermaid } from "./components/Mermaid";
import { Markdown } from "./components/Markdown";
import { CodeSnippet } from "./components/CodeSnippet";

const BACKEND_LABELS: Record<string, string> = {
  claude_cli: "Claude Code (no API key)",
  anthropic: "Anthropic API key",
};

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-edge bg-surface p-6 ${className}`}>{children}</div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-xs font-bold uppercase tracking-wider text-muted">{children}</div>
  );
}

export default function App() {
  const [backends, setBackends] = useState<Backends | null>(null);
  const [backend, setBackend] = useState("claude_cli");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);

  const [chat, setChat] = useState<ChatTurn[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getBackends()
      .then((b) => {
        setBackends(b);
        const def = b.available[b.default]
          ? b.default
          : Object.keys(b.available).find((k) => b.available[k]);
        if (def) setBackend(def);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, asking]);

  async function runExplain(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setError("");
    setLoading(true);
    setOverview(null);
    setChat([]);
    try {
      const data = await explain(query.trim(), backend);
      setOverview(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    setError("");
    setQuestion("");
    setChat((c) => [...c, { kind: "question", text: q }]);
    setAsking(true);
    try {
      const data = await followup(q, backend);
      setChat((c) => [...c, { kind: "answer", data }]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAsking(false);
    }
  }

  const backendUnavailable = backends && !backends.available[backend];

  return (
    <div className="mx-auto flex min-h-full max-w-5xl flex-col px-5 pb-40">
      <header className="pt-12 pb-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">
          Codebase <span className="text-accent-deep">Explainer</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-[15px] text-muted">
          Paste a GitHub URL to explain a repo, or describe a concept and let it find one.
        </p>
      </header>

      <div className="mt-6 flex items-center gap-3 text-sm text-muted">
        <span>Run on:</span>
        <select
          value={backend}
          onChange={(e) => setBackend(e.target.value)}
          className="rounded-lg border border-edge-strong bg-surface px-3 py-1.5 text-sm text-ink outline-none hover:border-accent-deep"
        >
          {backends &&
            Object.keys(backends.available).map((k) => (
              <option key={k} value={k} disabled={!backends.available[k]}>
                {(BACKEND_LABELS[k] ?? k) + (backends.available[k] ? "" : " — not available")}
              </option>
            ))}
        </select>
        {backendUnavailable && (
          <span className="text-[13px] text-red-600">
            {backend === "anthropic"
              ? "Set ANTHROPIC_API_KEY to enable this."
              : "Claude Code CLI not found."}
          </span>
        )}
      </div>

      <form onSubmit={runExplain} className="mt-3 flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="github.com/owner/repo  —or—  a clean example of a rate limiter"
          className="flex-1 rounded-xl border border-edge-strong bg-surface px-4 py-3 text-[15px] outline-none focus:border-accent-deep focus:ring-3 focus:ring-accent/30"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl border border-accent-deep bg-accent px-6 font-semibold text-[#08311f] transition hover:brightness-105 disabled:opacity-50"
        >
          {loading ? "Working…" : "Explain"}
        </button>
      </form>

      {loading && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-accent/45 bg-accent/12 px-4 py-3 text-accent-ink">
          <span className="h-4 w-4 animate-spin rounded-full border-[3px] border-accent/30 border-t-accent-deep" />
          Fetching tree, triaging files, analyzing code… (~20–40s)
        </div>
      )}
      {error && (
        <div className="mt-4 rounded-xl border border-red-500 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </div>
      )}

      {overview && (
        <main className="mt-6 flex flex-col gap-5">
          <Card className="!p-5">
            <div className="flex flex-wrap items-baseline gap-2">
              <a
                href={overview.repo.url}
                target="_blank"
                className="text-lg font-semibold text-accent-ink hover:underline"
              >
                {overview.repo.full_name}
              </a>
              {overview.mode === "B" && (
                <span className="rounded-full bg-accent/20 px-2.5 py-0.5 text-xs font-semibold text-accent-ink">
                  found via concept search
                </span>
              )}
            </div>
            {overview.repo.description && (
              <p className="mt-1 text-sm text-muted">{overview.repo.description}</p>
            )}
            <p className="mt-1 text-[13px] text-muted">
              ★ {overview.repo.stars} · {overview.repo.language} · {overview.file_count} files
            </p>
            {overview.selection?.reason && (
              <p className="mt-2 text-[13px]">
                <span className="font-semibold">Why this repo:</span> {overview.selection.reason}
              </p>
            )}
          </Card>

          <Card>
            <SectionLabel>Summary</SectionLabel>
            <Markdown text={overview.summary} />
          </Card>

          {overview.mermaid && (
            <Card>
              <SectionLabel>Architecture</SectionLabel>
              <Mermaid code={overview.mermaid} />
            </Card>
          )}

          {overview.sections.length > 0 && (
            <div>
              <SectionLabel>Code deep-dive</SectionLabel>
              <div className="flex flex-col gap-4">
                {overview.sections.map((sec, i) => (
                  <Card key={i}>
                    <h3 className="mb-2 text-base font-semibold text-ink">{sec.title}</h3>
                    <Markdown text={sec.explanation} />
                    {sec.snippets.length > 0 && (
                      <div className="mt-3 flex flex-col gap-3">
                        {sec.snippets.map((sn, j) => (
                          <CodeSnippet key={j} snippet={sn} />
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {chat.length > 0 && (
            <div>
              <SectionLabel>Conversation</SectionLabel>
              <div className="flex flex-col gap-4">
                {chat.map((turn, i) =>
                  turn.kind === "question" ? (
                    <div
                      key={i}
                      className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-accent/20 px-4 py-2.5 text-[15px]"
                    >
                      {turn.text}
                    </div>
                  ) : (
                    <Card key={i}>
                      <Markdown text={turn.data.answer} />
                      {turn.data.mermaid && (
                        <div className="mt-3">
                          <Mermaid code={turn.data.mermaid} />
                        </div>
                      )}
                      {turn.data.snippets.length > 0 && (
                        <div className="mt-3 flex flex-col gap-3">
                          {turn.data.snippets.map((sn, j) => (
                            <CodeSnippet key={j} snippet={sn} />
                          ))}
                        </div>
                      )}
                    </Card>
                  )
                )}
                {asking && (
                  <div className="flex items-center gap-3 text-muted">
                    <span className="h-4 w-4 animate-spin rounded-full border-[3px] border-accent/30 border-t-accent-deep" />
                    Thinking…
                  </div>
                )}
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </main>
      )}

      {overview && (
        <div className="fixed inset-x-0 bottom-0 z-10 border-t border-edge bg-cream/90 backdrop-blur">
          <form onSubmit={ask} className="mx-auto flex max-w-5xl gap-3 px-5 py-4">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a follow-up — e.g. “explain the auth flow” or “how does scoring work?”"
              className="flex-1 rounded-xl border border-edge-strong bg-surface px-4 py-3 text-[15px] outline-none focus:border-accent-deep focus:ring-3 focus:ring-accent/30"
            />
            <button
              type="submit"
              disabled={asking}
              className="rounded-xl border border-accent-deep bg-accent px-6 font-semibold text-[#08311f] transition hover:brightness-105 disabled:opacity-50"
            >
              Ask
            </button>
          </form>
        </div>
      )}
    </div>
  );
}