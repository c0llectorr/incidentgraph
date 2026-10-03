import { Outlet } from "react-router-dom";
import TopBar from "./TopBar";
import Sidebar from "./Sidebar";

export default function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-ig-bg">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-ig-blue focus:px-3 focus:py-1 focus:text-sm focus:text-white"
      >
        Skip to content
      </a>
      <TopBar />
      <div className="mx-auto flex w-full max-w-6xl flex-1">
        <Sidebar />
        <main id="main-content" className="min-w-0 flex-1 px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
