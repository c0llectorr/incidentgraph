import { AlertTriangle, CheckCircle2, CircleDashed, HelpCircle, MinusCircle } from "lucide-react";
import type { ReactNode } from "react";

type Tone = "neutral" | "positive" | "negative" | "pending" | "muted";

const TONE_STYLES: Record<Tone, { className: string; icon: ReactNode }> = {
  neutral: { className: "border-ig-border text-ig-navy", icon: <CircleDashed size={13} aria-hidden /> },
  positive: { className: "border-ig-green/50 text-ig-green", icon: <CheckCircle2 size={13} aria-hidden /> },
  negative: { className: "border-ig-danger/50 text-ig-danger", icon: <AlertTriangle size={13} aria-hidden /> },
  pending: { className: "border-ig-blue/50 text-ig-blue", icon: <HelpCircle size={13} aria-hidden /> },
  muted: { className: "border-ig-border text-ig-muted", icon: <MinusCircle size={13} aria-hidden /> },
};

interface StatusBadgeProps {
  status: string;
  tone?: Tone;
}

function toneForStatus(status: string): Tone {
  switch (status) {
    case "ready":
    case "succeeded":
    case "supported":
    case "user_verified":
    case "ok":
    case "supports":
      return "positive";
    case "failed":
    case "error":
    case "weakened":
    case "weakens":
      return "negative";
    case "indexing":
    case "running":
    case "queued":
    case "pending":
      return "pending";
    case "insufficient_evidence":
    case "awaiting_evidence":
    case "inconclusive":
      return "muted";
    default:
      return "neutral";
  }
}

/** Status is always text + icon + border — never color alone (PRD §6.3). */
export default function StatusBadge({ status, tone }: StatusBadgeProps) {
  const resolved = tone ?? toneForStatus(status);
  const { className, icon } = TONE_STYLES[resolved];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {icon}
      {status.replaceAll("_", " ")}
    </span>
  );
}
