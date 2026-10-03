import { useParams } from "react-router-dom";
import IncidentForm from "../../components/incidents/IncidentForm";

export default function IncidentCreatePage() {
  const { repositoryId = "" } = useParams();
  return (
    <div className="mx-auto max-w-2xl">
      <IncidentForm repositoryId={repositoryId} />
    </div>
  );
}
