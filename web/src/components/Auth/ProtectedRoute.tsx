import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent-500" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
