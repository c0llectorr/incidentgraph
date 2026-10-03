import { Workflow } from "lucide-react";
import RepositorySourceForm from "../../components/ingestion/RepositorySourceForm";

export default function LandingPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="max-w-2xl">
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-ig-navy">
          <Workflow size={22} className="text-ig-blue" aria-hidden />
          From failure to evidence-backed hypotheses
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ig-muted">
          IncidentGraph indexes your repository and connects incident evidence —
          logs, tracebacks, diffs — to the actual source code. It proposes
          competing, testable hypotheses, shows its evidence, and lets you
          question every conclusion. It assists you; it never certifies root
          causes or edits code.
        </p>
      </header>
      <RepositorySourceForm />
    </div>
  );
}
