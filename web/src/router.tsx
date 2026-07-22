import { Navigate, type RouteObject, useRoutes } from "react-router-dom";
import { ProtectedRoute } from "./components/Auth/ProtectedRoute";
import { RequireServer } from "./components/Auth/RequireServer";
import { SettingsLayout } from "./components/Settings/SettingsLayout";
import { AuditLogPage } from "./pages/AuditLog";
import { ChatPage } from "./pages/Chat";
import { HomePage } from "./pages/Home";
import { LoginPage } from "./pages/Login";
import { MatchRulesPage } from "./pages/MatchRules";
import { RuleProgramPage } from "./pages/RuleProgram";
import { ConfigPage } from "./pages/Settings";
import { SetupPage } from "./pages/Setup";
import { SyncsPage } from "./pages/Syncs";

export const routes: RouteObject[] = [
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/setup",
    element: (
      <ProtectedRoute>
        <SetupPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <HomePage />
        </RequireServer>
      </ProtectedRoute>
    ),
  },
  {
    path: "/syncs",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <SyncsPage />
        </RequireServer>
      </ProtectedRoute>
    ),
  },
  {
    path: "/chat",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <ChatPage />
        </RequireServer>
      </ProtectedRoute>
    ),
  },
  {
    path: "/chat/:sessionId",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <ChatPage />
        </RequireServer>
      </ProtectedRoute>
    ),
  },
  {
    path: "/audit",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <AuditLogPage />
        </RequireServer>
      </ProtectedRoute>
    ),
  },
  {
    path: "/settings",
    element: (
      <ProtectedRoute>
        <RequireServer>
          <SettingsLayout />
        </RequireServer>
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="config" replace /> },
      { path: "config", element: <ConfigPage /> },
      { path: "matching", element: <MatchRulesPage /> },
      { path: "matching/:ruleId", element: <RuleProgramPage /> },
    ],
  },
];

export function AppRoutes() {
  return useRoutes(routes);
}
