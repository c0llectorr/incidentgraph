import { Link, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import ChatPanel from "../../components/chat/ChatPanel";
import ErrorPanel from "../../components/common/ErrorPanel";
import Button from "../../components/common/Button";
import { useRepository } from "../../features/repositories/hooks";

export default function RepositoryWorkspacePage() {
  const { repositoryId = "" } = useParams();
  const { repository, error, loading } = useRepository(repositoryId);

  if (loading) {
    return <p role="status" className="text-sm text-ig-muted">Loading repository…</p>;
  }
  if (error || !repository) {
    return <ErrorPanel error={error ?? new Error("Repository not found.")} />;
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ig-navy">
            {repository.owner && repository.repo
              ? `${repository.owner}/${repository.repo}`
              : repository.source_reference.split(/[\\/]/).slice(-1)[0] ?? "Repository"}
          </h1>
          <p className="mt-0.5 font-mono text-xs text-ig-muted">
            index {repository.index_version ?? "—"} · {repository.file_count ?? "?"} files ·
            revision {repository.commit_sha?.slice(0, 10) ?? repository.source_type}
          </p>
        </div>
        <Link to={`/repositories/${repositoryId}/incidents/new`}>
          <Button>
            <Plus size={15} aria-hidden />
            New incident investigation
          </Button>
        </Link>
      </header>
      <ChatPanel repositoryId={repositoryId} repositoryStatus={repository.status} />
    </div>
  );
}
