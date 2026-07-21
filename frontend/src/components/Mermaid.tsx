import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "loose",
  theme: "base",
  themeVariables: {
    primaryColor: "#eafff5",
    primaryBorderColor: "#42f5a1",
    primaryTextColor: "#0b5f3c",
    lineColor: "#15a368",
    secondaryColor: "#f1ecdb",
    tertiaryColor: "#fdfcf5",
    fontFamily: "Segoe UI, sans-serif",
  },
});

let counter = 0;

export function Mermaid({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!code || !ref.current) return;
    let cancelled = false;
    setFailed(false);
    const id = "mmd-" + ++counter;
    mermaid
      .render(id, code)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (!code) return null;

  return (
    <div>
      <div ref={ref} className="mermaid-host flex justify-center overflow-auto" />
      {failed && (
        <pre className="mt-2 overflow-auto rounded-lg bg-surface2 p-3 text-xs text-muted">
          {code}
        </pre>
      )}
    </div>
  );
}