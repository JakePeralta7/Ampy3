import { useCallback, useEffect, useState } from "react";
import { systemInfoAPI } from "../api/system";

export function useVersion() {
  const [version, setVersion] = useState<string | null>(null);

  const fetchVersion = useCallback(async () => {
    try {
      const resp = await systemInfoAPI.getVersion();
      setVersion(resp.version);
    } catch {
      // sidebar simply renders no version if the API is unreachable
    }
  }, []);

  useEffect(() => {
    fetchVersion();
  }, [fetchVersion]);

  return { version };
}
