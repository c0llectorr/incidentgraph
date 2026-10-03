import { Network } from "lucide-react";
import { Link } from "react-router-dom";

export default function TopBar() {
  return (
    <header className="border-b border-ig-border bg-ig-surface">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2 font-semibold text-ig-navy">
          <Network size={18} className="text-ig-blue" aria-hidden />
          IncidentGraph
        </Link>
        <p className="hidden text-xs text-ig-muted sm:block">
          Evidence-grounded incident investigation — every claim inspectable
        </p>
      </div>
    </header>
  );
}
