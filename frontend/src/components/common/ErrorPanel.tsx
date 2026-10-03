import { AlertTriangle } from "lucide-react";
import { ApiError } from "../../lib/http";

interface ErrorPanelProps {
  error: unknown;
  onRetry?: () => void;
}

/** Actionable errors preserve user input (they never clear the form). */
export default function ErrorPanel({ error, onRetry }: ErrorPanelProps) {
  const isApi = error instanceof ApiError;
  const code = isApi ? error.body.code : "UNKNOWN_ERROR";
  const message =
    isApi ? error.body.message : error instanceof Error ? error.message : "Something went wrong.";
  const retryable = isApi ? error.body.retryable : true;

  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-lg border border-ig-danger/40 bg-ig-danger/5 px-4 py-3 text-sm"
    >
      <div className="flex items-center gap-2 font-medium text-ig-danger">
        <AlertTriangle size={15} aria-hidden />
        <span>
          {code.replaceAll("_", " ").toLowerCase()} — {message}
        </span>
      </div>
      {retryable && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="self-start rounded-md border border-ig-danger/40 px-3 py-1 text-xs font-medium text-ig-danger hover:bg-ig-danger/10"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
