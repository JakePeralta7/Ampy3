import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { LoadingSpinner } from "../ui/LoadingSpinner";

export function CheckSetup({ children }: { children: React.ReactNode }) {
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null);

  useEffect(() => {
    const checkSetup = async () => {
      try {
        const response = await fetch("/api/v1/settings/");
        if (response.ok) {
          const data = await response.json();
          setSetupComplete(data.secret_key_set === true);
        } else {
          setSetupComplete(false);
        }
      } catch {
        setSetupComplete(false);
      }
    };

    checkSetup();
  }, []);

  if (setupComplete === null) {
    return <LoadingSpinner />;
  }

  if (!setupComplete) {
    return <Navigate to="/setup" replace />;
  }

  return <>{children}</>;
}
