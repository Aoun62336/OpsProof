import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { getSession, logout } from "../lib/api";
import { LoginPage } from "../pages/LoginPage";
import { OverviewPage } from "../pages/OverviewPage";
import { IncidentsPage } from "../pages/IncidentsPage";
import { InvestigationPage } from "../pages/InvestigationPage";
import { ExperimentsPage } from "../pages/ExperimentsPage";
import { ExperimentDetailPage } from "../pages/ExperimentDetailPage";
import { ReportsPage } from "../pages/ReportsPage";
import { KubernetesPage } from "../pages/KubernetesPage";


export default function App() {
  const queryClient = useQueryClient();

  const session = useQuery({
    queryKey: ["auth", "session"],
    queryFn: getSession,
    retry: false,
    staleTime: 60_000,
  });

  if (session.isPending) {
    return (
      <div className="boot-screen" role="status">
        Connecting to OpsProof...
      </div>
    );
  }

  if (session.isError) {
    return (
      <div className="boot-screen boot-screen--error">
        <p>Unable to contact the OpsProof control API.</p>

        <button
          className="button button--secondary"
          type="button"
          onClick={() => void session.refetch()}
        >
          Retry connection
        </button>
      </div>
    );
  }

  if (!session.data) {
    return (
      <LoginPage
        onAuthenticated={(value) => {
          queryClient.setQueryData(
            ["auth", "session"],
            value,
          );
        }}
      />
    );
  }

  async function signOut() {
    await logout();

    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== "auth",
    });

    queryClient.setQueryData(
      ["auth", "session"],
      null,
    );
  }

  return (
    <BrowserRouter>
      <AppShell onSignOut={signOut}>
        <Routes>
          <Route path="/workloads" element={<KubernetesPage view="Workloads" />} />
          <Route path="/deployments" element={<KubernetesPage view="Deployments" />} />
          <Route path="/capacity" element={<KubernetesPage view="Capacity" />} />
          <Route path="/runbooks" element={<KubernetesPage view="Runbooks" />} />
          <Route path="/incidents/:fingerprint/investigate" element={<InvestigationPage />} />
          <Route path="/" element={<OverviewPage />} />

          <Route
            path="/incidents"
            element={<IncidentsPage />}
          />

          <Route
            path="/experiments"
            element={<ExperimentsPage />}
          />

          <Route
            path="/experiments/:runId"
            element={<ExperimentDetailPage />}
          />

          <Route
            path="/reports"
            element={<ReportsPage />}
          />

          <Route
            path="*"
            element={
              <section className="page">
                <h1>Page not found</h1>
                <p className="muted">
                  The requested workspace page does not exist.
                </p>
                <Link to="/">Return to overview</Link>
              </section>
            }
          />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
