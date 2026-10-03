import { createBrowserRouter } from "react-router-dom";
import AppShell from "../components/layout/AppShell";
import LandingPage from "./pages/LandingPage";
import IngestionPage from "./pages/IngestionPage";
import RepositoryWorkspacePage from "./pages/RepositoryWorkspacePage";
import IncidentCreatePage from "./pages/IncidentCreatePage";
import InvestigationPage from "./pages/InvestigationPage";
import ReportPage from "./pages/ReportPage";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/repositories/:repositoryId", element: <RepositoryWorkspacePage /> },
      {
        path: "/repositories/:repositoryId/ingestions/:jobId",
        element: <IngestionPage />,
      },
      {
        path: "/repositories/:repositoryId/incidents/new",
        element: <IncidentCreatePage />,
      },
      { path: "/incidents/:incidentId", element: <InvestigationPage /> },
      { path: "/incidents/:incidentId/report", element: <ReportPage /> },
    ],
  },
]);
