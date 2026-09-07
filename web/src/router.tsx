import { Navigate, type RouteObject, useRoutes } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RequireServer } from "./components/auth/RequireServer";
import { ExploreLayout } from "./components/Explore/ExploreLayout";
import { SettingsLayout } from "./components/Settings/SettingsLayout";
import { AuditLogPage } from "./pages/AuditLog";
import { ExploreDeezerPage } from "./pages/ExploreDeezerPage";
import { ExploreYTMusicPage } from "./pages/ExploreYTMusicPage";
import { HomePage } from "./pages/Home";
import { LoginPage } from "./pages/Login";
import { MatchRulesPage } from "./pages/MatchRules";
import { PlexSetupPage } from "./pages/PlexSetup";
import { RuleProgramPage } from "./pages/RuleProgram";
import { SourcesPage } from "./pages/Sources";
import { SyncsPage } from "./pages/Syncs";
import { TargetsPage } from "./pages/Targets";

const protectedServer = (element: React.ReactNode) => (
  <ProtectedRoute>
    <RequireServer>{element}</RequireServer>
  </ProtectedRoute>
);

export const routes: RouteObject[] = [
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/plex-setup",
    element: (
      <ProtectedRoute>
        <PlexSetupPage />
      </ProtectedRoute>
    ),
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
      <ProtectedRoute>
        <SettingsLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="sources" replace /> },
      { path: "sources", element: <SourcesPage /> },
      { path: "targets", element: <TargetsPage /> },
      { path: "matching", element: <MatchRulesPage /> },
      { path: "matching/:ruleId", element: <RuleProgramPage /> },
    ],
  },
];

export function AppRoutes() {
  return useRoutes(routes);
}
