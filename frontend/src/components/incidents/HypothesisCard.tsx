import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { Hypothesis } from "../../types/api";
import CitationChip from "../chat/CitationChip";
import StatusBadge from "../common/StatusBadge";

interface HypothesisCardProps {
  hypothesis: Hypothesis;
  onOpenCitation: (citation: import("../../types/api").SourceCitation) => void;
}

/** One competing hypothesis (PRD §2.2): explanation, supporting evidence,
 * contradicting/missing evidence — unverified status always visible. */
export default function HypothesisCard({ hypothesis, onOpenCitation }: HypothesisCardProps) {
  return (
    <article className="rounded-lg border border-ig-border bg-ig-surface p-5">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold text-ig-navy">{hypothesis.title}</h3>
        <StatusBadge status={hypothesis.status} />
      </header>
      <p className="mt-2 text-sm leading-relaxed text-ig-navy">{hypothesis.explanation}</p>

      {hypothesis.supporting_evidence.length > 0 ? (
        <div className="mt-4">
          <h4 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-ig-green">
            <ThumbsUp size={12} aria-hidden /> Supporting evidence
          </h4>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {hypothesis.supporting_evidence.map((citation) => (
              <CitationChip key={citation.source_id} citation={citation} onOpen={onOpenCitation} />
            ))}
          </div>
        </div>
      ) : (
        <p className="mt-3 text-xs text-ig-muted">
          No supporting citation survived validation — treat this hypothesis as
          speculative.
        </p>
      )}

      {hypothesis.contradicting_evidence.length > 0 ? (
        <div className="mt-3">
          <h4 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-ig-danger">
            <ThumbsDown size={12} aria-hidden /> Contradicting evidence
          </h4>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {hypothesis.contradicting_evidence.map((citation) => (
              <CitationChip key={citation.source_id} citation={citation} onOpen={onOpenCitation} />
            ))}
          </div>
        </div>
      ) : null}

      {hypothesis.missing_evidence.length > 0 ? (
        <div className="mt-3">
          <h4 className="text-xs font-medium uppercase tracking-wide text-ig-muted">
            Missing evidence
          </h4>
          <ul className="mt-1.5 list-disc pl-5 text-xs text-ig-muted">
            {hypothesis.missing_evidence.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}
