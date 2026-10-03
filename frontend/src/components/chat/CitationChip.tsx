import { FileCode2 } from "lucide-react";
import type { SourceCitation } from "../../types/api";

interface CitationChipProps {
  citation: SourceCitation;
  onOpen: (citation: SourceCitation) => void;
}

/** Clickable citation chip — opens the source drawer (PRD FR-23). */
export default function CitationChip({ citation, onOpen }: CitationChipProps) {
  const location =
    citation.start_line !== null
      ? `${citation.path}:${citation.start_line}${citation.end_line !== null ? `-${citation.end_line}` : ""}`
      : citation.path;
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-ig-blue/40 bg-ig-blue/5 px-2.5 py-0.5 font-mono text-xs text-ig-blue transition-colors duration-200 hover:bg-ig-blue/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue"
      title={`Inspect ${location}`}
    >
      <FileCode2 size={12} aria-hidden />
      <span className="truncate">{location}</span>
    </button>
  );
}
