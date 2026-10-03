import { X } from "lucide-react";
import type { SourceCitation } from "../../types/api";

interface SourceDrawerProps {
  citation: SourceCitation | null;
  onClose: () => void;
}

/** The citation inspector (PRD FR-23): retrieved excerpt, path, line range —
 * bounded so it never overwhelms the conversation (PRD §12.8). */
export default function SourceDrawer({ citation, onClose }: SourceDrawerProps) {
  if (!citation) return null;
  return (
    <aside
      role="complementary"
      aria-label="Cited source excerpt"
      className="w-80 shrink-0 overflow-y-auto rounded-lg border border-ig-border bg-ig-surface"
    >
      <div className="sticky top-0 flex items-center justify-between gap-2 border-b border-ig-border bg-ig-surface px-4 py-3">
        <h3 className="min-w-0 truncate font-mono text-xs text-ig-navy">
          {citation.path}
          {citation.start_line !== null ? `:${citation.start_line}${citation.end_line !== null ? `-${citation.end_line}` : ""}` : ""}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close source panel"
          className="rounded p-1 text-ig-muted hover:bg-ig-bg hover:text-ig-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue"
        >
          <X size={15} aria-hidden />
        </button>
      </div>
      <div className="px-4 py-3">
        <p className="mb-2 text-[11px] uppercase tracking-wide text-ig-muted">
          Retrieved excerpt
        </p>
        <pre className="overflow-x-auto rounded-md bg-ig-bg p-3 font-mono text-xs leading-relaxed text-ig-navy">
          {citation.excerpt ?? "(excerpt not retained)"}
        </pre>
        <p className="mt-3 break-all font-mono text-[11px] text-ig-muted">
          source: {citation.source_id}
        </p>
      </div>
    </aside>
  );
}
