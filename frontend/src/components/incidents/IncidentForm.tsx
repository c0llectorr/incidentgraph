import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bug, Send } from "lucide-react";
import Button from "../common/Button";
import ErrorPanel from "../common/ErrorPanel";
import TextArea from "../common/TextArea";
import Input from "../common/Input";
import { addEvidence, createIncident } from "../../features/incidents/api";

interface IncidentFormProps {
  repositoryId: string;
}

/** Screen 4 (PRD §12.4): incident creation. Missing values stay unknown —
 * optional fields are explicitly marked, never inferred. */
export default function IncidentForm({ repositoryId }: IncidentFormProps) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [service, setService] = useState("");
  const [traceback, setTraceback] = useState("");
  const [logs, setLogs] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const incident = await createIncident(repositoryId, {
        title,
        description,
        affected_endpoint: endpoint || null,
        affected_service: service || null,
      });
      if (traceback.trim()) {
        await addEvidence(incident.id, "traceback", traceback);
      }
      if (logs.trim()) {
        await addEvidence(incident.id, "log", logs);
      }
      navigate(`/incidents/${incident.id}`);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = !busy && title.trim().length > 0 && description.trim().length > 0;

  return (
    <section className="rounded-lg border border-ig-border bg-ig-surface p-6" aria-labelledby="incident-heading">
      <h2 id="incident-heading" className="flex items-center gap-2 text-lg font-semibold text-ig-navy">
        <Bug size={18} className="text-ig-blue" aria-hidden />
        New incident investigation
      </h2>
      <p className="mt-1 text-sm text-ig-muted">
        Describe the failure and supply evidence. The more specific the traceback,
        the sharper the retrieved code evidence.
      </p>

      <div className="mt-5 flex flex-col gap-4">
        <Input
          label="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Checkout endpoint returns 500"
          disabled={busy}
        />
        <TextArea
          label="Description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="What is failing, since when, and how was it observed?"
          disabled={busy}
          className="font-sans"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Affected endpoint (optional)"
            value={endpoint}
            onChange={(event) => setEndpoint(event.target.value)}
            placeholder="POST /orders/checkout — leave unknown if not known"
            disabled={busy}
          />
          <Input
            label="Affected service (optional)"
            value={service}
            onChange={(event) => setService(event.target.value)}
            placeholder="orders-service — leave unknown if not known"
            disabled={busy}
          />
        </div>
        <TextArea
          label="Python traceback (optional)"
          value={traceback}
          onChange={(event) => setTraceback(event.target.value)}
          rows={8}
          placeholder={"Traceback (most recent call last):\n  File \"app/x.py\", line 12, in handler\nFooError: boom"}
          disabled={busy}
        />
        <TextArea
          label="Log excerpt (optional)"
          value={logs}
          onChange={(event) => setLogs(event.target.value)}
          rows={6}
          placeholder="2026-10-03T10:15:04Z ERROR request_id=req_881 status=500 POST /orders"
          disabled={busy}
        />

        {error ? <ErrorPanel error={error} onRetry={submit} /> : null}

        <div className="flex justify-end">
          <Button onClick={submit} disabled={!canSubmit}>
            <Send size={15} aria-hidden />
            {busy ? "Creating…" : "Create incident"}
          </Button>
        </div>
      </div>
    </section>
  );
}
