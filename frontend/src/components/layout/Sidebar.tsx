import { Home } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Repository intake", icon: Home, end: true },
];

export default function Sidebar() {
  return (
    <nav aria-label="Primary" className="w-52 shrink-0 border-r border-ig-border bg-ig-surface px-3 py-4">
      <ul className="flex flex-col gap-1">
        {links.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue ${
                  isActive ? "bg-ig-blue/10 font-medium text-ig-blue" : "text-ig-muted hover:text-ig-navy"
                }`
              }
            >
              <Icon size={15} aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
