import { useParams } from "react-router-dom";
import IngestionProgress from "../../components/ingestion/IngestionProgress";
import EmptyState from "../../components/common/EmptyState";

export default function IngestionPage() {
  const { repositoryId = "", jobId = "" } = useParams();

  if (!repositoryId || !jobId) {
    return <EmptyState title="Missing job" body="No ingestion job was specified." />;
  }
  return <IngestionProgress jobId={jobId} repositoryId={repositoryId} />;
}
