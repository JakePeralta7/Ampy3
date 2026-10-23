import { Navigate, type RouteObject, useRoutes } from "react-router-dom";
import { CheckSetup } from "./components/auth/CheckSetup";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RequireServer } from "./components/auth/RequireServer";
import { ExploreLayout } from "./components/Explore/ExploreLayout";
import { SettingsLayout } from "./components/Settings/SettingsLayout";
import { AuditLogPage } from "./pages/AuditLog";
import { ExploreDeezerPage } from "./pages/ExploreDeezerPage";
import { ExploreYTMusicPage } from "./pages/ExploreYTMusicPage";
import { HomePage } from "./pages/Home";
import { InfrastructureSettingsPage } from "./pages/InfrastructureSettings";
import { LoginPage } from "./pages/Login";
import { MatchRulesPage } from "./pages/MatchRules";
import { NetworkSettingsPage } from "./pages/NetworkSettings";
import { RuleProgramPage } from "./pages/RuleProgram";
import { SecuritySettingsPage } from "./pages/SecuritySettings";
import { ServerSettingsPage } from "./pages/ServerSettings";
import { UnifiedSetupPage } from "./pages/UnifiedSetup";
import { SourcesPage } from "./pages/Sources";
import { SyncsPage } from "./pages/Syncs";
import { TargetsPage } from "./pages/Targets";

const protectedServer = (element: React.ReactNode) => (
  <CheckSetup>
    <ProtectedRoute>
      <RequireServer>{element}</RequireServer>
    </ProtectedRoute>
  </CheckSetup>
);

export const routes: RouteObject[] = [
  {
    path: "/setup",
    element: <UnifiedSetupPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: protectedServer(<HomePage />),
  },
  {
    path: "/syncs",
    element: protectedServer(<SyncsPage />),
  },
  {
    path: "/explore",
    element: protectedServer(<ExploreLayout />),
    children: [
      { index: true, element: <Navigate to="ytmusic" replace /> },
      { path: "ytmusic", element: <ExploreYTMusicPage /> },
      { path: "deezer", element: <ExploreDeezerPage /> },
    ],
  },
  {
    path: "/audit",
    element: protectedServer(<AuditLogPage />),
  },
  {
    path: "/settings",
    element: (
      <CheckSetup>
        <ProtectedRoute>
          <SettingsLayout />
        </ProtectedRoute>
      </CheckSetup>
    ),
    children: [
      { index: true, element: <Navigate to="sources" replace /> },
      { path: "sources", element: <SourcesPage /> },
      { path: "targets", element: <TargetsPage /> },
      { path: "matching", element: <MatchRulesPage /> },
      { path: "matching/:ruleId", element: <RuleProgramPage /> },
      { path: "network", element: <NetworkSettingsPage /> },
      { path: "infrastructure", element: <InfrastructureSettingsPage /> },
      { path: "security", element: <SecuritySettingsPage /> },
      { path: "server", element: <ServerSettingsPage /> },
    ],
  },
];

export function AppRoutes() {
  return useRoutes(routes);
}
