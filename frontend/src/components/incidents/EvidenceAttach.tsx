import { useState } from "react";
import { Paperclip } from "lucide-react";
import Button from "../common/Button";
import ErrorPanel from "../common/ErrorPanel";
import TextArea from "../common/TextArea";
import { addEvidence } from "../../features/incidents/api";

interface EvidenceAttachProps {
  incidentId: string;
  onAttached: () => void;
}

/** Lets the user attach (more) evidence to an existing incident — required
 * after an `awaiting_evidence` stop, and for refining any investigation
 * (FR-27; re-analysis runs on new evidence per FR-37). */
export default function EvidenceAttach({ incidentId, onAttached }: EvidenceAttachProps) {
  const [traceback, setTraceback] = useState("");
  const [logs, setLogs] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [attached, setAttached] = useState(0);

  const attach = async () => {
    setBusy(true);
    setError(null);
    try {
      if (traceback.trim()) {
        await addEvidence(incidentId, "traceback", traceback);
      }
      if (logs.trim()) {
        await addEvidence(incidentId, "log", logs);
      }
      const count = (traceback.trim() ? 1 : 0) + (logs.trim() ? 1 : 0);
      if (count === 0) {
        throw new Error("Paste a traceback or log excerpt before attaching.");
      }
      setTraceback("");
      setLogs("");
      setAttached((previous) => previous + count);
      onAttached();
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Attach incident evidence"
      className="rounded-lg border border-ig-border bg-ig-surface p-4"
    >
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ig-navy">
        <Paperclip size={14} className="text-ig-blue" aria-hidden />
        Attach evidence {attached > 0 ? `(${attached} artifact${attached > 1 ? "s" : ""} added)` : ""}
      </h3>
      <div className="mt-3 flex flex-col gap-3">
        <TextArea
          label="Python traceback"
          value={traceback}
          onChange={(event) => setTraceback(event.target.value)}
          rows={5}
          placeholder={'Traceback (most recent call last):\n  File "app/x.py", line 12, in handler\nFooError: boom'}
          disabled={busy}
        />
        <TextArea
          label="Log excerpt"
          value={logs}
          onChange={(event) => setLogs(event.target.value)}
          rows={4}
          placeholder="2026-10-04T10:15:04Z ERROR request_id=req_881 status=500 POST /orders"
          disabled={busy}
        />
        {error ? <ErrorPanel error={error} /> : null}
        <div>
          <Button variant="secondary" onClick={attach} disabled={busy}>
            {busy ? "Attaching…" : "Attach evidence"}
          </Button>
        </div>
      </div>
    </section>
  );
}
