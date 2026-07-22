import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

const ERROR_MESSAGES: Record<string, string> = {
  not_authorized: "Your Plex account is not authorized to access this application.",
  auth_failed: "Authentication failed. Please try again.",
  token_exchange_failed: "Could not complete Plex authentication. Please try again.",
  profile_fetch_failed: "Could not retrieve your Plex profile. Please try again.",
  missing_pin: "Session expired. Please try logging in again.",
  invalid_pin: "Session expired. Please try logging in again.",
};

export function LoginPage() {
  const { login, requireAuth, loading } = useAuth();
  const [searchParams] = useSearchParams();
  const errorKey = searchParams.get("error");
  const errorMessage = errorKey ? ERROR_MESSAGES[errorKey] || "An error occurred." : null;

  if (!loading && !requireAuth) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-app">
      <div className="w-full max-w-sm mx-auto px-4">
        <div className="bg-bg-surface rounded-xl border border-border shadow-sm p-8 text-center">
          <div className="mb-6">
            <div className="h-14 w-14 rounded-xl bg-accent-500 text-accent-fg flex items-center justify-center font-bold text-xl mx-auto">
              A
            </div>
          </div>

          <h1 className="text-xl font-semibold text-fg mb-1">Ampy3</h1>
          <p className="text-sm text-fg-muted mb-8">Sign in with your Plex account</p>

          {errorMessage && (
            <div className="mb-6 px-4 py-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">
              {errorMessage}
            </div>
          )}

          <button
            type="button"
            onClick={login}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-[#e5a00d] hover:bg-[#cc8f00] text-black font-medium text-sm transition-colors duration-fast cursor-pointer"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5"
              fill="currentColor"
              role="img"
              aria-label="Plex"
            >
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 2.25c5.385 0 9.75 4.365 9.75 9.75S17.385 21.75 12 21.75 2.25 17.385 2.25 12 6.615 2.25 12 2.25zm-2.25 5v9.5l7.25-4.75L9.75 7.25z" />
            </svg>
            Sign in with Plex
          </button>
        </div>

        <p className="text-center text-xs text-fg-subtle mt-4">
          Only the server owner can access this application.
        </p>
      </div>
    </div>
  );
}
