import type { Snippet } from "../types";

/** A code excerpt with file path, line range, and gutter line numbers. */
export function CodeSnippet({ snippet }: { snippet: Snippet }) {
  const lines = snippet.code.split("\n");
  return (
    <div className="overflow-hidden rounded-lg border border-edge bg-[#1f2d27]">
      <div className="flex items-center justify-between border-b border-black/30 bg-[#16201b] px-3 py-1.5">
        <span className="font-mono text-xs text-accent">{snippet.path}</span>
        <span className="font-mono text-[11px] text-white/40">
          L{snippet.start}-{snippet.end}
        </span>
      </div>
      <pre className="overflow-auto p-3 text-[12.5px] leading-relaxed">
        <code className="font-mono">
          {lines.map((ln, i) => (
            <div key={i} className="flex">
              <span className="mr-3 select-none text-right text-white/25" style={{ minWidth: "2.5em" }}>
                {snippet.start + i}
              </span>
              <span className="whitespace-pre text-[#dfeee7]">{ln || " "}</span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  );
}