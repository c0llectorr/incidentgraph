import { useParams } from "react-router-dom";
import IngestionProgress from "../../components/ingestion/IngestionProgress";
import EmptyState from "../../components/common/EmptyState";

export default function IngestionPage() {
  const { repositoryId = "", jobId = "" } = useParams();

  // Route params must be real IDs; literal "undefined"/"null" strings mean a
  // caller navigated with missing data — show the empty state, don't poll.
  const usable = (value: string) => value.length > 0 && !["undefined", "null"].includes(value);
  if (!usable(repositoryId) || !usable(jobId)) {
    return (
      <EmptyState
        title="No ingestion to show"
        body="Start an ingestion from the repository intake page."
      />
    );
  }
  return <IngestionProgress jobId={jobId} repositoryId={repositoryId} />;
}
