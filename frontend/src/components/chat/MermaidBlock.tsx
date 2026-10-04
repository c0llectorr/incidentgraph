import { useEffect, useState } from "react";
import { Check, Copy, GitFork } from "lucide-react";

type MermaidModule = typeof import("mermaid");

let mermaidModule: MermaidModule | null = null;

/** Lazy-load mermaid only when a diagram actually appears — keeps the main
 * bundle free of the (large) rendering library. Initialized once. */
async function getMermaid(): Promise<MermaidModule["default"]> {
  if (mermaidModule === null) {
    const loaded = await import("mermaid");
    loaded.default.initialize({
      startOnLoad: false,
      theme: "neutral",
      securityLevel: "strict",
    });
    mermaidModule = loaded;
  }
  return mermaidModule.default;
}

let renderSequence = 0;

interface MermaidBlockProps {
  code: string;
}

/** Diagram block for ```mermaid fenced code in assistant answers: renders
 * the diagram, and always offers a one-click copy of the raw code so the
 * user can paste it into the Mermaid live editor. */
export default function MermaidBlock({ code }: MermaidBlockProps) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSvg(null);
    setError(null);
    getMermaid()
      .then((mermaid) => mermaid.render(`ig-mermaid-${++renderSequence}`, code))
      .then(({ svg: rendered }) => {
        if (!cancelled) setSvg(rendered);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2_000);
  };

  return (
    <figure className="not-prose my-3 overflow-hidden rounded-lg border border-ig-border bg-ig-surface">
      <figcaption className="flex items-center justify-between gap-2 border-b border-ig-border bg-ig-bg px-3 py-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-ig-muted">
          <GitFork size={13} aria-hidden />
          Mermaid diagram — paste the code into{" "}
          <a
            href="https://mermaid.live"
            target="_blank"
            rel="noreferrer"
            className="text-ig-blue underline"
          >
            mermaid.live
          </a>{" "}
          to view it
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md border border-ig-border bg-ig-surface px-2 py-1 text-xs font-medium text-ig-navy hover:border-ig-blue hover:text-ig-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue"
        >
          {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </figcaption>
      <div className="max-h-96 overflow-auto px-3 py-3">
        {svg ? (
          <div
            className="[&_.node]:font-sans [&_svg]:mx-auto [&_svg]:max-w-full"
            data-testid="mermaid-render"
            // Mermaid output with securityLevel "strict" is sanitized SVG.
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : error ? (
          <div>
            <p role="alert" className="mb-2 text-xs text-ig-danger">
              This Mermaid snippet could not be rendered — copy the code below and fix it in the
              Mermaid editor.
            </p>
            <pre className="overflow-x-auto rounded-md bg-ig-bg p-3 font-mono text-xs text-ig-navy">
              {code}
            </pre>
          </div>
        ) : (
          <p role="status" className="text-xs text-ig-muted">
            Rendering diagram…
          </p>
        )}
      </div>
    </figure>
  );
}
