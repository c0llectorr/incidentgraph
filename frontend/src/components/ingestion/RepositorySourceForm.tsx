import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp, Link2, ShieldAlert } from "lucide-react";
import Button from "../common/Button";
import ErrorPanel from "../common/ErrorPanel";
import Input from "../common/Input";
import {
  createRepositoryFromUrl,
  createRepositoryFromZip,
  startIngestion,
} from "../../features/ingestion/api";

const MAX_UPLOAD_BYTES = 10_485_760;

interface RepositorySourceFormProps {
  onIngestionStarted?: (repositoryId: string, jobId: string) => void;
}

/** Screen 1 (PRD §12.4): landing / repository intake with scope note and
 * privacy statement. Server limits are mirrored client-side with limit text. */
export default function RepositorySourceForm({ onIngestionStarted }: RepositorySourceFormProps) {
  const navigate = useNavigate();
  const [githubUrl, setGithubUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const repository = file
        ? await createRepositoryFromZip(file)
        : await createRepositoryFromUrl(githubUrl);
      const started = await startIngestion(repository.id);
      setJobId(started.job_id);
      onIngestionStarted?.(repository.id, started.job_id);
      navigate(`/repositories/${repository.id}/ingestions/${started.job_id}`);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  const urlInvalid = githubUrl.length > 0 && !/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+/.test(githubUrl);
  const fileTooLarge = file !== null && file.size > MAX_UPLOAD_BYTES;
  const canSubmit = !busy && (file ? !fileTooLarge : githubUrl.length > 0 && !urlInvalid);

  return (
    <section className="rounded-lg border border-ig-border bg-ig-surface p-6" aria-labelledby="intake-heading">
      <h2 id="intake-heading" className="text-lg font-semibold text-ig-navy">
        Index a repository
      </h2>
      <p className="mt-1 text-sm text-ig-muted">
        Submit a public GitHub URL or upload a ZIP archive. Python-first: Python,
        Markdown, and text files are indexed.
      </p>

      <div className="mt-5 flex flex-col gap-4">
        <Input
          label="Public GitHub repository URL"
          placeholder="https://github.com/owner/repo"
          value={githubUrl}
          onChange={(event) => {
            setGithubUrl(event.target.value);
            setFile(null);
          }}
          aria-invalid={urlInvalid}
          hint={
            urlInvalid
              ? "Expected shape: https://github.com/owner/repo (optionally /tree/branch)."
              : "Private repositories are not supported in this MVP."
          }
          disabled={file !== null || busy}
        />

        <div className="flex items-center gap-3 text-xs text-ig-muted">
          <span className="h-px flex-1 bg-ig-border" aria-hidden />
          or
          <span className="h-px flex-1 bg-ig-border" aria-hidden />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="zip-upload" className="text-[13px] font-medium text-ig-navy">
            ZIP archive upload
          </label>
          <div className="flex items-center gap-3">
            <label
              htmlFor="zip-upload"
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-ig-border bg-ig-surface px-3 py-2 text-sm text-ig-navy hover:border-ig-blue"
            >
              <FileUp size={15} aria-hidden />
              {file ? file.name : "Choose a .zip file"}
            </label>
            <input
              id="zip-upload"
              type="file"
              accept=".zip,application/zip"
              className="sr-only"
              disabled={busy}
              onChange={(event) => {
                const selected = event.target.files?.[0];
                if (selected) {
                  setFile(selected);
                  setGithubUrl("");
                }
              }}
            />
            {fileTooLarge ? (
              <span role="alert" className="text-xs text-ig-danger">
                File exceeds the 10 MB upload limit.
              </span>
            ) : null}
          </div>
        </div>

        {error ? <ErrorPanel error={error} onRetry={submit} /> : null}

        <div className="flex items-start gap-2 rounded-md bg-ig-bg px-3 py-2 text-xs text-ig-muted">
          <ShieldAlert size={14} className="mt-0.5 shrink-0 text-ig-muted" aria-hidden />
          <p>
            Privacy: your repository content and any incident evidence you later supply
            may be sent to the configured model providers (Groq for generation, the
            configured embedding endpoint) when cloud inference is enabled. Secrets
            are filtered before indexing, but detection is heuristic — do not submit
            repositories containing credentials.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <Button onClick={submit} disabled={!canSubmit}>
            <Link2 size={15} aria-hidden />
            {busy ? "Starting…" : "Validate and ingest"}
          </Button>
        </div>
        {jobId ? <p className="text-xs text-ig-muted">Ingestion job {jobId} started.</p> : null}
      </div>
    </section>
  );
}
