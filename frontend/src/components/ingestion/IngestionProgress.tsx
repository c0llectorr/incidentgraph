import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import Button from "../common/Button";
import ErrorPanel from "../common/ErrorPanel";
import TraceLineLoader from "../common/TraceLineLoader";

interface IngestionProgressProps {
  jobId: string;
  repositoryId: string;
}

/** Screen 2 (PRD §12.4): staged progress view driven entirely by backend
 * events, with retry-on-error behavior. Navigation is SPA-based — no full
 * page reload. */
export default function IngestionProgress({ jobId, repositoryId }: IngestionProgressProps) {
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);
  const [key, setKey] = useState(0);

  const onComplete = useCallback(
    (status: string) => {
      if (status === "succeeded") {
        navigate(`/repositories/${repositoryId}`, { replace: true });
      } else {
        setFailed(true);
      }
    },
    [navigate, repositoryId],
  );  return (
    <section className="flex flex-col gap-4" aria-label="Ingestion progress">
      <header>
        <h1 className="text-xl font-semibold text-ig-navy">Indexing repository</h1>
        <p className="text-sm text-ig-muted">
          Repository <code className="font-mono text-xs">{repositoryId}</code> — job{" "}
          <code className="font-mono text-xs">{jobId}</code>
        </p>
      </header>
      <TraceLineLoader key={key} jobId={jobId} onComplete={onComplete} />
      {failed ? (
        <div className="flex flex-col gap-3">
          <ErrorPanel
            error={new Error("Ingestion did not complete. You can retry the job.")}
          />
          <div>
            <Button
              variant="secondary"
              onClick={() => {
                setFailed(false);
                setKey((previous) => previous + 1);
              }}
            >
              Retry monitoring
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
